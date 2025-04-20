import requests
import pandas as pd
import numpy as np
import os
import sys
import shutil
import argparse
import subprocess
import resource
import time
import re
from functools import wraps

import logging
logger = logging.getLogger(__name__)

# https://crates.io/api/v1/crates?category=api-bindings&page=50&per_page=100
# &sort=recent-downloads
BASE_URL = "https://crates.io/api/v1"
SUB_PROCESS_TIMEOUT = 60 * 30
RUST_TOOLCHAIN = "nightly-2024-02-08-x86_64-unknown-linux-gnu"
EXCLUDE_CRATE = {
    "google-api-proto", # This crate is so big that it takes too long to clone and build 
}
# cargo update serde --precise 1.0.203
# cargo update zerofrom --precise 0.1.5
# cargo update litemap --precise 0.7.4
# cargo update native-tls --precise 0.2.13
# cargo build -Zcheck-cfg

def time_profiler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_real = time.perf_counter()
        start_ru = resource.getrusage(resource.RUSAGE_SELF)

        result = func(*args, **kwargs)

        end_real = time.perf_counter()
        end_ru = resource.getrusage(resource.RUSAGE_SELF)

        real_time = end_real - start_real
        user_time = end_ru.ru_utime - start_ru.ru_utime
        sys_time = end_ru.ru_stime - start_ru.ru_stime
        logging.info(f"Real time: {real_time:.2f}s, User time: {user_time:.2f}s, Sys time: {sys_time:.2f}s")

        return (result, real_time, user_time, sys_time)
    return wrapper

def subprocess_time_profiler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_real = time.perf_counter()
        start_ru = resource.getrusage(resource.RUSAGE_CHILDREN)

        result = func(*args, **kwargs)

        end_real = time.perf_counter()
        end_ru = resource.getrusage(resource.RUSAGE_CHILDREN)

        real_time = end_real - start_real
        user_time = end_ru.ru_utime - start_ru.ru_utime
        sys_time = end_ru.ru_stime - start_ru.ru_stime
        logging.info(f"Real time: {real_time:.2f}s, User time: {user_time:.2f}s, Sys time: {sys_time:.2f}s")
        return (result, real_time, user_time, sys_time)
    return wrapper
    
def parse_time_str(s: str) -> list[float]:
    pattern = r":(\d+\.?\d*)"
    numbers = re.findall(pattern, s)
    # convert to float
    result = [float(num) for num in numbers]
    return result

# get the total number of crates in a category
def get_total_crates(category: str) -> int:
    url = f"{BASE_URL}/crates?category={category}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        total_crates = data['meta']['total']
        return total_crates
    else:
        print(f"Error: {response.status_code}")
        return 0

@time_profiler
def get_crates(page: int, per_page: int, category: str) -> list:
    url = f"{BASE_URL}/crates?category={category}&page={page}&per_page={per_page}&sort=recent-downloads"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        crates = data['crates']
        return crates
    else:
        print(f"Error: {response.status_code}")
        return []
    pass

@subprocess_time_profiler
def clone_crate(url: str, dirname: str) -> bool:
    cwd = os.path.join(os.getcwd(), "proj_collect")
    logging.debug(f"\nClone {url} to {cwd}")
    try:
        result = subprocess.run(["git", "clone", url, dirname], cwd=cwd, timeout=SUB_PROCESS_TIMEOUT)
        if result.returncode == 0:
            logging.info(f"Clone {url} success")
            return True
        else:
            logging.error(f"Clone {url} failed")
            logging.error(f"Error stderr: \n{result.stderr}")
            logging.error(f"Error stdout: \n{result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        logging.error(f"Clone {url} timeout")
        return False
    except Exception as e:
        logging.error(f"Clone {url} failed: {e}")
        return False

@subprocess_time_profiler
def init_submodule(dirname: str) -> bool:
    cwd = os.path.join(os.getcwd(), "proj_collect", dirname)
    logging.debug(f"\nInit submodule in {cwd}")
    try:
        result = subprocess.run(["git", "submodule", "update", "--init", "--recursive"], cwd=cwd, timeout=SUB_PROCESS_TIMEOUT)
        if result.returncode == 0:
            logging.info(f"Init submodule in {cwd} success")
            return True
        else:
            logging.error(f"Init submodule in {cwd} failed")
            logging.error(f"Error stderr: \n{result.stderr}")
            logging.error(f"Error stdout: \n{result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        logging.error(f"Clone {url} timeout")
        return False
    except Exception as e:
        logging.error(f"Clone {url} failed: {e}")
        return False

def override_toolchain(dirname: str) -> bool:
    cwd = os.path.join(os.getcwd(), "proj_collect", dirname)
    try:
        result = subprocess.run(["rustup", "override", "set", RUST_TOOLCHAIN], cwd=cwd, timeout=SUB_PROCESS_TIMEOUT)
        subprocess.run(["cargo", "update", "serde", "--precise", "1.0.203"], cwd=cwd, timeout=SUB_PROCESS_TIMEOUT)
        subprocess.run(["cargo", "update", "native-tls", "--precise", "0.2.13"], cwd=cwd, timeout=SUB_PROCESS_TIMEOUT)
        subprocess.run(["cargo", "update", "zerofrom", "--precise", "0.1.5"], cwd=cwd, timeout=SUB_PROCESS_TIMEOUT)
        subprocess.run(["cargo", "update", "litemap", "--precise", "0.7.4"], cwd=cwd, timeout=SUB_PROCESS_TIMEOUT)
        subprocess.run(["cargo", "vendor"], cwd=cwd, timeout=SUB_PROCESS_TIMEOUT)
        if result.returncode == 0:
            logging.info(f"Override toolchain in {cwd} success")
            return True
        else:
            logging.error(f"Override toolchain in {cwd} failed")
            logging.error(f"Error stderr: \n{result.stderr}")
            logging.error(f"Error stdout: \n{result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        logging.error(f"Clone {url} timeout")
        return False
    except Exception as e:
        logging.error(f"Clone {url} failed: {e}")
        return False
    pass

def cargo_clean(dirname: str) -> bool:
    cwd = os.path.join(os.getcwd(), "proj_collect", dirname)
    logging.debug(f"\nClean {dirname} in {cwd}")
    result = subprocess.run(["cargo", "clean"], cwd=cwd, timeout=SUB_PROCESS_TIMEOUT)
    if result.returncode == 0:
        logging.info(f"Clean {dirname} success")
        return True
    else:
        logging.error(f"Clean {dirname} failed")
        logging.error(f"Error stderr: \n{result.stderr}")
        logging.error(f"Error stdout: \n{result.stdout}")
        return False
    pass

@subprocess_time_profiler
def build_crate(dirname: str) -> bool:
    cwd = os.path.join(os.getcwd(), "proj_collect", dirname)
    logging.info(f"\nBuild {dirname} in {cwd}")
    try:
        result = subprocess.run(["cargo", "build", "-Zcheck-cfg"], cwd=cwd, timeout=SUB_PROCESS_TIMEOUT)
        if result.returncode == 0:
            logging.info(f"Build {dirname} success")
            return True
        else:
            logging.error(f"Build {dirname} failed")
            logging.error(f"Error stderr: \n{result.stderr}")
            logging.error(f"Error stdout: \n{result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        logging.error(f"Clone {url} timeout")
        return False
    except Exception as e:
        logging.error(f"Clone {url} failed: {e}")
        return False
    pass

@subprocess_time_profiler
def gen_crate_ir(dirname: str) -> bool:
    cwd = os.path.join(os.getcwd(), "proj_collect", dirname)
    logging.info(f"Gen IR {dirname} in {cwd}")
    try:
        result = subprocess.run(["cargo", "ffi-checker"], cwd=cwd, timeout=SUB_PROCESS_TIMEOUT)
        if result.returncode == 0:
            logging.info(f"Gen IR {dirname} success")
            return True
        else:
            logging.error(f"Gen IR {dirname} failed")
            logging.error(f"Error stderr: \n{result.stderr}")
            logging.error(f"Error stdout: \n{result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        logging.error(f"Clone {url} timeout")
        return False
    except Exception as e:
        logging.error(f"Clone {url} failed: {e}")
        return False

def check_valid(dirname: str) -> bool:
    cwd = os.path.join(os.getcwd(), "proj_collect", dirname, "target", "entry_points")
    crate_ffi_record_files = []
    for root,dirs,files in os.walk(cwd, topdown=False):
        for name in files:
            crate_ffi_record_files.append(os.path.join(root, name))
    ffi_cnt = 0
    for file in crate_ffi_record_files:
        with open(file, "r") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("FFI: "):
                    ffi_cnt += 1
    if ffi_cnt <= 0:
        return False
    else:
        return True

@subprocess_time_profiler
def analyze_crate(dirname: str) -> bool:
    cwd = os.path.join(os.getcwd(), "proj_collect", dirname)
    logging.info(f"Analyze {dirname} in {cwd}")
    try:
        result = subprocess.run(["cargo", "ffi-analyzer"], cwd=cwd, timeout=SUB_PROCESS_TIMEOUT)
        if result.returncode == 0:
            logging.info(f"Analyze {dirname} success")
            return True
        else:
            logging.error(f"Analyze {dirname} failed")
            logging.error(f"Error stderr: \n{result.stderr}")
            logging.error(f"Error stdout: \n{result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        logging.error(f"Clone {url} timeout")
        return False
    except Exception as e:
        logging.error(f"Clone {url} failed: {e}")
        return False


def cp_result(dirname: str):
    cwd = os.path.join(os.getcwd(), "proj_collect", dirname)
    dest_dir = os.path.join(os.getcwd(), "result_collect", dirname)
    shutil.rmtree(dest_dir, ignore_errors=True)
    os.mkdir(dest_dir)
    shutil.copyfile(os.path.join(cwd, "call_graph.dot"), os.path.join(dest_dir, "call_graph.dot"))
    shutil.copyfile(os.path.join(cwd, "control_flow_graph.dot"), os.path.join(dest_dir, "control_flow_graph.dot"))
    shutil.copyfile(os.path.join(cwd, "interface.json"), os.path.join(dest_dir, "interface.json"))
    pass

@subprocess_time_profiler
def render_graph(dirname: str) -> bool:
    dest_dir = os.path.join(os.getcwd(), "result_collect", dirname)
    call_graph = os.path.join(dest_dir, "call_graph.dot")
    control_flow_graph = os.path.join(dest_dir, "control_flow_graph.dot")
    try:
        if os.path.exists(call_graph):
            # 4000000
            if os.path.getsize(call_graph) > 4000000:
                logging.error(f"Call graph {call_graph} is too large")
                return False
            result = subprocess.run(["dot", "-Tpdf", call_graph, "-o", os.path.join(dest_dir, "call_graph.pdf")], timeout=SUB_PROCESS_TIMEOUT)
            if result.returncode == 0:
                logging.info(f"Render {call_graph} success")
            else:
                logging.error(f"Render {call_graph} failed")
                logging.error(f"Error stderr: \n{result.stderr}")
                logging.error(f"Error stdout: \n{result.stdout}")
                return False
        if os.path.exists(control_flow_graph):
            if os.path.getsize(control_flow_graph) > 3000000:
                logging.error(f"Call graph {call_graph} is too large")
                return False
            result = subprocess.run(["dot", "-Tpdf", control_flow_graph, "-o", os.path.join(dest_dir, "control_flow_graph.pdf")], timeout=SUB_PROCESS_TIMEOUT)
            if result.returncode == 0:
                logging.info(f"Render {control_flow_graph} success")
            else:
                logging.error(f"Render {control_flow_graph} failed")
                logging.error(f"Error stderr: \n{result.stderr}")
                logging.error(f"Error stdout: \n{result.stdout}")
                return False
    except subprocess.TimeoutExpired:
        logging.error(f"Clone {url} timeout")
        return False
    except Exception as e:
        logging.error(f"Clone {url} failed: {e}")
        return False
    return True

def init():
    os.mkdir("proj_collect")
    os.mkdir("result_collect")
    logging.info("Create directories: proj_collect, result_collect")
    df = pd.DataFrame(columns=[
        "name", "repository", "dirname", 
        "valid_proj",
        "build_success", 
        "normal_build_time", 
        "ffi_checker_success",
        "ffi_checker_build_time", 
        "ffi_checker_analysis_time"
    ])

    total_crates = get_total_crates("api-bindings")
    logging.info(f"Total crates: {total_crates}")
    per_page = 100
    total_pages = total_crates // per_page + 1
    for page in range(1, total_pages + 1):
        print(f"\rPage: {page}/{total_pages}", end="")
        crates, *time_info = get_crates(page, per_page, "api-bindings")
        crates_info = []
        for crate in crates:
            name = crate['name']
            repository: str = crate['repository']
            if repository is None:
                continue
            if not repository.startswith("https://github"):
                continue
            if name in EXCLUDE_CRATE:
                continue
            repository = repository.rstrip("/")
            dirname = repository.split("/")[-1].split(".")[0]
            if dirname is None or len(dirname) == 0:
                logging.info(f"\nError: Crate: {name} No directory name found")
            valid_proj = False
            build_success = False
            normal_build_time = None
            ffi_checker_success = False
            ffi_checker_build_time = None
            ffi_checker_analysis_time = None
            crate_info = {
                "name": name,
                "repository": repository,
                "dirname": dirname,
                "valid_proj": valid_proj,
                "build_success": build_success,
                "normal_build_time": normal_build_time,
                "ffi_checker_success": ffi_checker_success,
                "ffi_checker_build_time": ffi_checker_build_time,
                "ffi_checker_analysis_time": ffi_checker_analysis_time
            }
            crates_info.append(crate_info)
        tmp_df = pd.DataFrame(crates_info)
        df = pd.concat([df, tmp_df], ignore_index=True)
    df.drop_duplicates(subset=["repository"], keep="first", inplace=True)
    df.to_csv("crates.csv", index=False)
    logging.info("\nCrates list saved to crates.csv")
    pass

def build(args: argparse.Namespace) -> bool:
    df = pd.read_csv("crates.csv")
    skip_cnt = args.skip
    limit = args.limit
    target_df = df.iloc[skip_cnt:skip_cnt+limit]
    if args.valid_only:
        print("Build Valid Proj Only")
        target_df = target_df[target_df["valid_proj"] == True]
    all_success = True
    for row in target_df.itertuples():
        logging.debug(f"Row: {row}")
        logging.info("Building crate: {}".format(row.name))
        index = row.Index
        name = row.name
        repository = row.repository
        dirname = row.dirname
        ret_clone, *clone_time = clone_crate(repository, dirname)
        if not ret_clone:
            all_success = False
            logging.error(f"Clone {name} failed")
            continue
        ret_submodule, *submodule_time = init_submodule(dirname)
        if not ret_submodule:
            all_success = False
            logging.error(f"Init submodule {name} failed")
            continue
        ret_override = override_toolchain(dirname)

        # download deps
        ret_clean = cargo_clean(dirname)
        ret_build, *build_time = build_crate(dirname)

        if not (ret_clone and ret_submodule and ret_override and ret_clean and ret_build):
            all_success = False
            logging.error(f"Build {name} failed")
            crate_dir = os.path.join(os.getcwd(), "proj_collect", dirname)
            shutil.rmtree(crate_dir, ignore_errors=True)
            continue

        normal_build_time_str = f"real_time:{build_time[0]:.2f}s, user_time:{build_time[1]:.2f}s, sys_time:{build_time[2]:.2f}s"

        ret_clean = cargo_clean(dirname)
        ret_gen_ir, *ffi_checker_build_time_info = gen_crate_ir(dirname)

        ffi_checker_build_time_str = f"real_time:{ffi_checker_build_time_info[0]:.2f}s, user_time:{ffi_checker_build_time_info[1]:.2f}s, sys_time:{ffi_checker_build_time_info[2]:.2f}s"

        if not ret_gen_ir or not ret_clean:
            all_success = False
            logging.error(f"Generate IR for {name} failed")
            crate_dir = os.path.join(os.getcwd(), "proj_collect", dirname)
            shutil.rmtree(crate_dir, ignore_errors=True)
            continue

        ret_valid = check_valid(dirname)

        if ret_valid:
            ret_analysis, *analysis_time = analyze_crate(dirname)
            if not ret_analysis:
                all_success = False
                logging.error(f"Analyze {name} failed")
                continue
            cp_result(dirname)
            ffi_checker_analysis_time_str = f"real_time:{analysis_time[0]:.2f}s, user_time:{analysis_time[1]:.2f}s, sys_time:{analysis_time[2]:.2f}s"
            df.loc[index, "ffi_checker_analysis_time"] = ffi_checker_analysis_time_str
            render_graph(dirname)
        else:
            crate_dir = os.path.join(os.getcwd(), "proj_collect", dirname)
            shutil.rmtree(crate_dir, ignore_errors=True)
        
        logging.debug(f"Build {name}\tIndex:{index}\tresult:{ret_build}")
        df.loc[index, "build_success"] = ret_build
        df.loc[index, "valid_proj"] = ret_valid
        df.loc[index, "ffi_checker_success"] = ret_gen_ir
        df.loc[index, "ffi_checker_build_time"] = ffi_checker_build_time_str
        df.loc[index, "normal_build_time"] = normal_build_time_str

        # save data each time
        df.to_csv("crates.csv", index=False)
    
@time_profiler
def clean(args: argparse.Namespace) -> bool:
    if args.skip is not None and args.limit is not None:
        df = pd.read_csv("crates.csv")
        skip_cnt = args.skip
        limit = args.limit
        df = df.iloc[skip_cnt:skip_cnt+limit]
        for index, row in df.iterrows():
            logging.info("Cleaning crate: {}".format(row['name']))
            dirname = row['dirname']
            if os.path.exists(os.path.join("proj_collect", dirname)):
                shutil.rmtree(os.path.join("proj_collect", dirname), ignore_errors=True)
                logging.info(f"Clean {dirname} success")
            else:
                logging.info(f"Clean {dirname} failed, directory does not exist")
    elif args.skip is None and args.limit is None:
        if os.path.exists("crates.csv"):
            os.remove('crates.csv')
            logging.info('file deleted')
        else:
            logging.info("File does not exists")
        if os.path.exists("proj_collect"):
            shutil.rmtree("proj_collect", ignore_errors=True)
            logging.info('proj_collect directory deleted')
        else:
            logging.info("proj_collect Directory does not exists")
        if os.path.exists("result_collect"):
            shutil.rmtree("result_collect", ignore_errors=True)
            logging.info('result_collect directory deleted')
        else:
            logging.info("result_collect Directory does not exists")
    else:
        logging.info("Please provide both --skip and --limit or none of them")
        return False

    logging.info("Clean up completed")
    return True

@time_profiler
def main():
    logging.basicConfig(
        filename='new.log',
        filemode='w',
        level=logging.DEBUG
    )
    parser = argparse.ArgumentParser(
                    prog='collect_proj',
                    description='A Script to eval FFI Checker',
                    epilog='init first then build, analysis, clean'
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize the crates list")

    build_parser = subparsers.add_parser("build", help="Rebuild all crates in the crates list")
    build_parser.add_argument("--skip", type=int, default=0, help="Skip the first n crates")
    build_parser.add_argument("--limit", type=int, default=10, help="Limit the number of crates to build")
    build_parser.add_argument("--valid-only", type=bool, default=False, help="Build only valid crates")

    analysis_parser = subparsers.add_parser("analysis", help="Analyze the crates list")
    analysis_parser.add_argument("--skip", type=int, default=0, help="Skip the first n crates")
    analysis_parser.add_argument("--limit", type=int, default=10, help="Limit the number of crates to analyze")
    analysis_parser.add_argument("--output", type=str, default="result_collect", help="Output directory for the analysis results")

    clean_parser =subparsers.add_parser("clean", help="Clean the crates target directory")
    clean_parser.add_argument("--skip", type=int, help="Skip the first n crates")
    clean_parser.add_argument("--limit", type=int, help="Limit the number of crates to clean")

    args = parser.parse_args()  
    
    if args.command == "init":
        logging.info("Init")
        init()
    elif args.command == "build":
        logging.info("Build")
        build(args)
    elif args.command == "clean":
        logging.info("Clean")
        clean(args)
    else:
        logging.info(parser.format_help())
    return

if __name__ == '__main__':
    main()

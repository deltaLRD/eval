# FFI-Checker Eval

## 使用 gh 配置好git的github登录

```bash
sudo apt update
sudo apt upgrade
sudo apt install gh 
sudo apt install libssl-dev pkg-config build-essential cmake libudev-dev -y
gh auth login
```

## 安装LLVM17
```bash
cd ~
wget https://github.com/llvm/llvm-project/releases/download/llvmorg-17.0.6/clang+llvm-17.0.6-x86_64-linux-gnu-ubuntu-22.04.tar.xz
tar -xvf clang+llvm-17.0.6-x86_64-linux-gnu-ubuntu-22.04.tar.xz
mv clang+llvm-17.0.6-x86_64-linux-gnu-ubuntu-22.04 llvm17
```

## 将LLVM17加入环境变量

向 ~/.bashrc 文件末尾添加
注意这个需要再rust的环境变量前面
```bash
export PATH="/home/ubuntu/llvm17/bin:$PATH"
```

## 安装rust

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
. "$HOME/.cargo/env"
```

## 安装固定的toolchain

```bash
rustup toolchain install nightly-2024-02-08-x86_64-unknown-linux-gnu
rustup default nightly-2024-02-08-x86_64-unknown-linux-gnu
rustup component add rustc-dev llvm-tools-preview
```

## 获取 ffi-checker 并安装

```bash
git clone https://github.com/deltaLRD/ffi-checker.git
cd ffi-checker
cargo install --path .
cd ~
```

## 获取 ffi-anlysis

```bash
```

## 安装miniconda

```bash
mkdir -p ~/miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm ~/miniconda3/miniconda.sh
source ~/miniconda3/bin/activate
conda init --all
source .bashrc
```

## 获取eval

```bash
git clone https://github.com/deltaLRD/eval.git
cd eval
conda env create -f environment.yaml
conda activate ffi_eval 
```

## Eval
```bash
python collect_proj.py init
python collect_proj.py build --skip=0 --limit=10
```
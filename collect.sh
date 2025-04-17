#!/bin/bash
# 功能：递归移动proj_collect项目目录下的特定文件到result_collect对应目录
# 使用方式：保存为move_files.sh，添加执行权限后运行（chmod +x move_files.sh）

# 遍历所有项目目录（例如proj_collect/proj1、proj_collect/proj2）
for proj_path in ./proj_collect/*; do
    # 提取项目名称（去除路径末尾的斜杠）
    proj_name=$(basename "${proj_path%/}")
    echo "${proj_name}"
    echo "${proj_path}"
    # 创建目标目录（若不存在）
    dest_dir="./result_collect/${proj_name}"
    echo "${dest_dir}"
    mkdir -p "$dest_dir"
    
    # 递归查找并移动三种目标文件[1,5](@ref)
    #find "$proj_path"  -name "call_graph.dot" -o -name "control_flow_graph.dot" -o -name "interface.txt" $ \
    #    -exec mv -v {} "$dest_dir" \;
    find "${proj_path}" -name "call_graph.dot" -exec mv {} "${dest_dir}/" \;
    find "${proj_path}" -name "control_flow_graph.dot" -exec mv {} "${dest_dir}/" \;
    find "${proj_path}" -name "interface.txt" -exec mv {} "${dest_dir}/" \;
done

echo "文件移动完成！请检查目标目录：./result_collect/"

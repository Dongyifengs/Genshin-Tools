import codecs  # 导入codecs模块，用于处理文件编码
import json  # 导入json模块，用于处理JSON数据
import os  # 导入os模块，用于操作文件和目录
import re  # 导入re模块，用于正则表达式匹配
import shutil  # 导入shutil模块，用于文件操作
import bs4  # 导入bs4库，用于HTML解析
import requests  # 导入requests库，用于发送HTTP请求
from rich.progress import track  # 导入rich库中的进度条组件
import subprocess  # 导入subprocess模块，用于执行外部命令

SPINE_COM_FILE = r"D:\Program Files\Spine\spine.com"  # Spine软件的路径
PROXY_HOST_PORT = ("127.0.0.1", 7890)  # 代理服务器的主机和端口配置


# 生成Spine项目的函数，传入项目目录的路径
def generator_spine_project(project_dir: str):
    atlas_file = None  # 初始化变量，用于存储.atlas文件的路径
    json_file = None  # 初始化变量，用于存储.json文件的路径
    for file in os.listdir(project_dir):
        if file.endswith(".atlas"):
            atlas_file = os.path.join(project_dir, file)
        if file.endswith(".json"):
            json_file = os.path.join(project_dir, file)
    if atlas_file is None:
        print("找不到atlas文件")
        return
    if json_file is None:
        print("找不到json文件")
        return

    proxy_host, proxy_port = PROXY_HOST_PORT  # 从配置中获取代理服务器的主机和端口
    output_dir = os.path.join(project_dir, "out")  # 输出目录的路径
    if os.path.isdir(output_dir):
        shutil.rmtree(output_dir)  # 如果输出目录已存在，删除它
    os.mkdir(output_dir)  # 创建输出目录

    images_dir = os.path.join(output_dir, "images")  # 图片目录的路径
    if os.path.isdir(images_dir):
        shutil.rmtree(images_dir)  # 如果图片目录已存在，删除它
    os.mkdir(images_dir)  # 创建图片目录

    with open(atlas_file, "r", encoding="utf-8") as fp_atlas_file:
        content = fp_atlas_file.read()  # 读取.atlas文件的内容

    part_name = ""  # 初始化部分名称变量
    part = {}  # 初始化部分数据字典
    scale = None  # 初始化缩放比例变量
    content_split = content.split("\n")  # 按行分割内容
    png_file_name = content_split[0].replace(".png", "")  # 获取图片文件名
    for line in content_split:
        if ":" in line:
            line_sp = line.replace("\t", "").replace(": ", ":").split(":")  # 分割键值对
            key, value = tuple(line_sp)
            part[part_name][key] = value
            if key == "scale":
                scale = float(value)  # 如果键是"scale"，设置缩放比例
        else:
            part_name = line
            part[part_name] = {}  # 以部分名称创建子字典
    if scale is None:
        print("\t找不到scale，使用默认值1.0")  # 如果缩放比例未找到，输出提示并使用默认值
        scale = 1.0

    with open(json_file, "r", encoding='utf-8') as fp_atlas_file:
        json_content = json.loads(fp_atlas_file.read())  # 读取.json文件的内容并解析为JSON
    spine_version = json_content['skeleton']['spine']  # 获取Spine版本信息
    if "-from-" in spine_version:
        spine_version = spine_version.split("-from-")[1]  # 处理Spine版本字符串

    spine_project_file = os.path.join(output_dir, f"{png_file_name}-v{spine_version}.spine")  # Spine项目文件路径

    subprocess.call(
        [SPINE_COM_FILE, "-x", f"{proxy_host}:{proxy_port}", "-u", spine_version, "-i", project_dir, '-o', project_dir,
         '-c', atlas_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # 调用Spine命令行工具生成项目
    subprocess.call([SPINE_COM_FILE, "-x", f"{proxy_host}:{proxy_port}", "-u", spine_version, "-i", project_dir, '-o',
                     spine_project_file, '-s', str(scale), '-r', json_file], stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)  # 调用Spine命令行工具生成Spine项目文件

    for file in os.listdir(project_dir):
        if file.replace(".png", "") in part.keys():
            os.rename(os.path.join(project_dir, file), os.path.join(images_dir, file))  # 移动图片文件到图片目录


# 解析.atlas文件内容的函数
def parser_atlas(content: str) -> str:
    return str(codecs.escape_decode(content)[0], 'utf-8')


BASE_URL = "https://act.mihoyo.com"  # 基础URL
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 "
      "Safari/537.36 Edg/119.0.0.0")  # 用户代理字符串

default_headers = {"user-agent": UA}  # 默认HTTP请求头

main_index_url = input("请输入页面URL：")

# main_index_url = "https://act.mihoyo.com/ys/event/e20230624preview/index.html"  # 主页面的URL

page_url = main_index_url.replace(BASE_URL, "").replace("index.html", "")  # 页面URL路径
main_index_html = requests.get(main_index_url, headers=default_headers).content.decode(
    "utf-8")  # 发送HTTP请求获取主页面内容并解码为UTF-8

bs = bs4.BeautifulSoup(main_index_html, features='lxml')  # 使用BeautifulSoup解析HTML
head = bs.find("head")  # 查找<head>元素
title = head.find_all("title")[0].text  # 获取页面标题
# 检查目录是否存在，如果存在则删除
if os.path.isdir(title):
    shutil.rmtree(title)
# 创建一个新的目录
os.mkdir(title)

vendors_js_url = None

# 在HTML头部查找包含JavaScript代码的标签
for ele in head.find_all("script"):
    try:
        src: str = ele['src']
    except KeyError:
        pass
    else:
        # 如果脚本标签包含“vendors”关键字，则获取其URL
        if "vendors" in src:
            vendors_js_url = BASE_URL + src

# 如果找不到vendors.js文件，则输出错误信息并退出
if vendors_js_url is None:
    print("找不到vendors.js")
    exit(-1)

# 下载vendors.js文件并保存到本地
with open(os.path.join(title, "vendors.js"), "wb") as fp:
    vendors_js_content = requests.get(vendors_js_url).content
    fp.write(vendors_js_content)

# 将vendors.js文件内容解码为UTF-8，并按行拆分
vendors_js_lines = vendors_js_content.decode("utf-8").splitlines()
vendors_js_str = "".join(vendors_js_lines[1:len(vendors_js_lines)])  # 跳过第一行并将其余行连接为字符串

string_literals: list[str] = re.findall(r'["\'](.*?)["\']', vendors_js_str)  # 查找JavaScript代码中的字符串字面值

spine_str = ""
datas = {}

# 遍历每个字符串字面值
for string_literal in track(string_literals, description="处理中..."):
    if ".png" in string_literal and not string_literal.startswith("http"):
        spine_str = string_literal
        lines = spine_str.split("\\n")
        name = lines[0].replace(".png", "")
        images = []

        # 获取包含图片名称的行
        for line in lines:
            if line.endswith(".png"):
                images.append(line.replace(".png", ""))
        index = vendors_js_str.find(spine_str)
        start_find_index = index + len(spine_str) + 36 + 1
        json_str = None

        # 寻找包含JSON数据的文本
        for i in range(start_find_index, len(vendors_js_str)):
            s = vendors_js_str[i]
            if s == "'":
                json_str = vendors_js_str[start_find_index: i]
                break
        if json_str is None:
            print(f"{name}找不到完整的json文本")
            continue

        try:
            md5s = {}
            for i in images:
                md5 = re.findall(f"images/{i}.(.*?)..png", vendors_js_str)[0]
                md5s[i] = md5
        except IndexError:
            print(f"{name}找不到图片")
            continue
        else:
            img_urls = {}
            for img_name, md5 in md5s.items():
                img_url = f"{BASE_URL}{page_url}images/{img_name}.{md5}..png"
                img_urls[img_name] = img_url
        datas[name] = (spine_str, json_str, img_urls)

# 遍历数据并下载相关资源
for k, v in track(datas.items(), description="下载中并处理中..."):
    print(k, "正在处理...")
    save_path = os.path.join(title, k)

    # 检查目录是否存在，如果存在则删除
    if os.path.isdir(save_path):
        shutil.rmtree(save_path)
    # 创建一个新的目录
    os.mkdir(save_path)
    s, j, i = v
    atlas_path = os.path.join(save_path, f"{k}.atlas")
    json_path = os.path.join(save_path, f"{k}.json")

    # 创建并写入atlas文件
    with open(atlas_path, "w", encoding='utf-8') as fp:
        fp.write(parser_atlas(s))
    # 创建并写入json文件
    with open(json_path, "w", encoding='utf-8') as fp:
        # print(j)
        data = json.loads(j)
        data['skeleton']['images'] = "./images/"
        fp.write(json.dumps(data, ensure_ascii=False, indent=4))
    for name, url in i.items():
        img_path = os.path.join(save_path, f"{name}.png")

        # 下载并保存图片
        with open(img_path, "wb") as fp:
            fp.write(requests.get(url).content)
    generator_spine_project(save_path)

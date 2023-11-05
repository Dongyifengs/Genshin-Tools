import base64
import codecs
import re
import subprocess
from collections import namedtuple
from typing import Any, List

from bs4 import BeautifulSoup
from requests import get
import os
from shutil import rmtree
from rich.progress import Progress, ProgressColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from hashlib import md5
import json

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 "
      "Safari/537.36 Edg/119.0.0.0")
headers = {"user-agent": UA}
SPINE_COM_FILE = r"D:\Program Files\Spine\spine.com"  # Spine软件的路径
PROXY_HOST_PORT = ("127.0.0.1", 7890)  # 代理服务器的主机和端口配置

URL = namedtuple("URL", ["protocol", "base", "href", "filename"])


def list_to_str(input_list: list[Any]) -> str:
    """
    将列表转换为str
    :param input_list: 输入列表
    :return: 输出一个使用逗号分隔的字符串，如[XXX, XXX, XXX]
    """
    return '[' + ", ".join([str(item) for item in input_list]) + ']'


class AtlasRegion:
    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return f"AtlasRegion({self.name})"


class AtlasPage:
    def __init__(self, name: str, regions: list[AtlasRegion]):
        self.name = name
        self.regions = regions
        self.img = None

    def __str__(self):
        return f"AtlasPage(name = {self.name}, regions = {list_to_str(self.regions)}, img = {self.img})"


class AtlasContent:
    def __init__(self, pages: list[AtlasPage], original: str, original_json: dict[Any, Any], scale: float = 1.0):
        self.pages = pages
        self.scale = scale
        self.original = original
        self.original_json = original_json

    def __str__(self):
        return f"AtlasContent(pages = {list_to_str(self.pages)}, scale = {self.scale})"

    def get_name(self) -> str:
        """
        返回项目名称
        :return: 项目名称
        """
        return self.pages[0].name


def url_parser(url_str: str) -> URL:
    """
    将URL格式化
    :param url_str: 文本类型的url
    :return: 输出一个URL对象，包含了输入url的协议、域名、地址、文件名
    """
    url_str_split = url_str.split("://")
    protocol = url_str_split[0]
    url_without_protocol = url_str_split[1]
    url_without_protocol_split = url_without_protocol.split("/")
    base = url_without_protocol_split[0]
    href = "/".join(url_without_protocol_split[1: len(url_without_protocol_split) - 1])
    filename = url_without_protocol_split[-1]
    return URL(protocol, base, href, filename)


def abs_url(url: str, access_url: URL) -> str:
    """
    将相对路径url改为绝对路径url
    :param url: url
    :param access_url: 格式化后的根url
    :return: 绝对路径url
    """
    if url.startswith("/"):
        return access_url.protocol + "://" + access_url.base + url
    if url.startswith("http"):
        return url
    return access_url.protocol + "://" + access_url.base + "/" + access_url.href + "/" + url


def get_all_string(js_code: str) -> list[str]:
    """
    获取js中所有的字符串
    :param js_code: js代码
    :return: 一个有两个元素的元组，第一个元素是使用双引号的字符串，第二个是使用单引号的字符串
    """
    return re.findall(r'"(.*?)"', js_code)


def get_all_image_base64(js_code: str) -> list[bytes]:
    """
    获取js代码中所有的图片base64
    :param js_code: js代码
    :return: 一个包含图片二进制的列表
    """
    code_length = len(js_code)
    last_index = 0
    images = []
    while True:
        index = js_code.find("data:image/png;base64,", last_index, code_length)
        if index == -1:
            break
        symbol = js_code[index - 1]
        b64_content = ""
        for i in range(index, code_length):
            s = js_code[i]
            if s == symbol:
                break
            b64_content += s
        images.append(base64.b64decode(b64_content.replace("data:image/png;base64,", "")))
        last_index = index + 1
    return images


def parser_atlas(content: str) -> AtlasContent:
    """
    解析atlas
    :param content: str格式的atlas
    :return: atlas对象
    """
    atlas_content = str(codecs.escape_decode(content)[0], 'utf-8').replace("\t", "")
    result = AtlasContent([], atlas_content, {})
    now_page = None
    for line in atlas_content.splitlines():
        if line == "":
            continue
        if line.endswith(".png"):
            # 页
            if now_page is not None:
                result.pages.append(now_page)
            page_name = line.replace(".png", "")
            now_page = AtlasPage(page_name, [])
            continue
        if ":" in line:
            # 属性
            if line.startswith("scale:"):
                scale = float(line.replace(" ", "").replace("scale:", ""))
                result.scale = scale
            continue
        # 区域
        now_page.regions.append(AtlasRegion(line))
    result.pages.append(now_page)
    return result


def parser_spine_version(version: str) -> str:
    """
    转换spine版本
    :param version: 原始版本字符串
    :return: 可用的一个版本（最新）
    """
    if "-from-" in version:
        return version.split("-from-")[1]
    return version


def rm_default_create(path: os.PathLike | str):
    """
    若文件夹存在则删除并重新创建
    :param path: 文件夹路径
    """
    if os.path.isdir(path):
        rmtree(path)
    os.mkdir(path)


def parser_index_page(main_index_url: str):
    columns: List[ProgressColumn] = [TextColumn("{task.description}"),
                                     BarColumn(),
                                     TaskProgressColumn(show_speed=True),
                                     TimeRemainingColumn(elapsed_when_finished=True)
                                     ]
    progress = Progress(*columns, refresh_per_second=60)
    progress.start()
    # 获取页面 -> 获取vendors.js -> 获取atlas 获取json 获取图片 -> 获取base64 -> 下载图片 -> 将base64保存为图片 -> 解开图片 -> 生成项目
    main_progress_bar_task_id = progress.add_task("获取页面中...", total=7)
    main_index_url_parser = url_parser(main_index_url)

    bs = BeautifulSoup(get(main_index_url, headers=headers).content.decode('utf-8'), features='lxml')
    index_head = bs.find("head")
    main_name = index_head.find("title").text
    vendors_js_url = None
    rm_default_create(main_name)
    os.chdir(main_name)
    progress.update(main_progress_bar_task_id, completed=1, description="获取vendors.js中...")
    for script_ele in bs.find_all("script"):
        try:
            src_url = script_ele['src']
        except KeyError:
            ...
        else:
            if "vendors" in src_url:
                vendors_js_url = src_url
                break
    if vendors_js_url is None:
        print("找不到vendors.js")
        exit(-1)
    with open("vendors.js", "wb") as vendors_js_fp:
        vendors_js_binary = get(abs_url(vendors_js_url, main_index_url_parser), headers=headers).content
        vendors_js_fp.write(vendors_js_binary)
    vendors_js_content = vendors_js_binary.decode("utf-8")
    vendors_js_lines = vendors_js_content.splitlines()
    vendors_js_content = "".join(vendors_js_lines[1:len(vendors_js_lines)])
    double = get_all_string(vendors_js_content)
    vendors_js_length = len(vendors_js_content)
    progress.update(main_progress_bar_task_id, completed=2, description="获取Atlas、JSON、图片中...")
    parser_vendors_js_progress_task_id = progress.add_task(description="解析vendors.js...")
    projects = []
    # Atlas解析、JSON解析
    for i in progress.track(double, task_id=parser_vendors_js_progress_task_id):
        if ".png" in i and not i.startswith("http") and not i.startswith("images/"):
            atlas = parser_atlas(i)
            # 计算json所在位置
            json_start_index = vendors_js_content.find(i) + len(i) + 37
            json_content = ""
            for json_index in range(json_start_index, vendors_js_length):
                s = vendors_js_content[json_index]
                if s == "'":
                    break
                json_content += s
            atlas.original_json = json.loads(json_content)
            atlas.original_json['skeleton']['images'] = "./images"
            regions = []
            for page in atlas.pages:
                for region in page.regions:
                    regions.append(region)
                page_name = page.name
                # 计算page图片所在位置
                try:
                    page_img_md5 = re.findall(f"images/{page_name}.(.*?)..png", vendors_js_content)[0]
                except IndexError:
                    print(f"{atlas.get_name()} 缺少 {page_name}.png")
                else:
                    page.img = abs_url(f"images/{page_name}.{page_img_md5}..png", main_index_url_parser)
            projects.append(atlas)
    progress.remove_task(parser_vendors_js_progress_task_id)
    progress.update(main_progress_bar_task_id, completed=3, description="获取base64图片中...")
    # base64解析
    base64_images = get_all_image_base64(vendors_js_content)
    progress.update(main_progress_bar_task_id, completed=4, description="下载图片中...")
    download_image_progress_task_id = progress.add_task(description="下载...")
    for project in progress.track(projects, task_id=download_image_progress_task_id):
        project_name = project.get_name()
        progress.update(download_image_progress_task_id, description=f"正在下载{project_name}...")
        download_page_image_task_id = progress.add_task(description="下载...")
        rm_default_create(project_name)
        for page in progress.track(project.pages, task_id=download_page_image_task_id):
            if page.img is None:
                continue
            with open(os.path.join(project_name, f"{page.name}.png"), "wb") as fp:
                fp.write(get(page.img).content)
        progress.remove_task(download_page_image_task_id)
        with open(os.path.join(project_name, f"{project_name}.atlas"), "w", encoding='utf-8') as fp:
            fp.write(project.original)
        with open(os.path.join(project_name, f"{project_name}.json"), "w", encoding='utf-8') as fp:
            fp.write(json.dumps(project.original_json, ensure_ascii=False, indent=4))
    progress.remove_task(download_image_progress_task_id)
    progress.update(main_progress_bar_task_id, completed=5, description="保存base64图片中...")
    rm_default_create("base64Images")
    save_b64_image_progress_task_id = progress.add_task(description="保存...")
    for img in progress.track(base64_images, task_id=save_b64_image_progress_task_id):
        with open(os.path.join("base64Images", md5(img).hexdigest()[0:6] + ".png"), "wb") as fp:
            fp.write(img)
    progress.remove_task(save_b64_image_progress_task_id)
    progress.update(main_progress_bar_task_id, completed=6, description="正在解开图片并生成项目...")
    proxy_host, proxy_port = PROXY_HOST_PORT
    unpack_create_project_progress_task_id = progress.add_task("解开图片并生成项目...")
    for project in progress.track(projects, task_id=unpack_create_project_progress_task_id):
        project_name = project.get_name()
        spine_version = parser_spine_version(project.original_json['skeleton']['spine'])
        atlas_file = os.path.join(project_name, f"{project_name}.atlas")
        json_file = os.path.join(project_name, f"{project_name}.json")
        out_dir = os.path.join(project_name, "out")
        rm_default_create(out_dir)
        spine_project_file = os.path.join(out_dir, "project.spine")
        images_path = os.path.join(out_dir, "images")
        rm_default_create(images_path)
        inner_task_id = progress.add_task(total=2, description="正在解开图片...")
        subprocess.call(
            [SPINE_COM_FILE, "-x", f"{proxy_host}:{proxy_port}", "-u", spine_version, "-i", project_name, '-o',
             project_name,
             '-c', atlas_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for page in project.pages:
            for region in page.regions:
                try:
                    os.rename(os.path.join(project_name, f"{region.name}.png"), os.path.join(images_path, f"{region.name}.png"))
                except FileNotFoundError:
                    ...
        progress.update(task_id=inner_task_id, completed=1, description="正在创建项目...")
        subprocess.call(
            [SPINE_COM_FILE, "-x", f"{proxy_host}:{proxy_port}", "-u", spine_version, "-i", project_name, '-o',
             spine_project_file, '-s', str(project.scale), '-r', json_file], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        progress.update(task_id=inner_task_id, completed=2, description="完成...")
        progress.remove_task(inner_task_id)
    progress.remove_task(unpack_create_project_progress_task_id)
    progress.update(main_progress_bar_task_id, completed=7, description="完成...")
    progress.stop()


if __name__ == "__main__":
    # parser_index_page("https://act.mihoyo.com/ys/event/e20230805preview/index.html")
    parser_index_page(input("请输入页面URL："))

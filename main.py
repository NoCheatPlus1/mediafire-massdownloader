import requests
import os
import re
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

DOWNLOAD_ROOT = "downloads"
MAX_WORKERS = 20
RETRIES = 3

session = requests.Session()


def get_folder_key(url):
    m = re.search(r'/folder/([^/]+)', url)
    return m.group(1) if m else None


def resolve_download_link(file_page):
    r = session.get(file_page)
    m = re.search(r'href="(https://download[^"]+)"', r.text)
    return m.group(1) if m else None


def download_file(file_url, path):

    for attempt in range(RETRIES):
        try:
            direct = resolve_download_link(file_url)

            if not direct:
                print("Failed:", file_url)
                return

            name = direct.split("/")[-1].split("?")[0]
            filepath = os.path.join(path, name)

            os.makedirs(path, exist_ok=True)

            r = session.get(direct, stream=True)

            total = int(r.headers.get("content-length", 0))

            with open(filepath, "wb") as f, tqdm(
                desc=name,
                total=total,
                unit="B",
                unit_scale=True,
                unit_divisor=1024
            ) as bar:

                for chunk in r.iter_content(1024 * 64):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))

            return

        except Exception as e:
            if attempt == RETRIES - 1:
                print("Failed after retries:", file_url)
            else:
                print("Retrying", file_url)


def get_files(folder_key):

    url = f"https://www.mediafire.com/api/1.5/folder/get_content.php?folder_key={folder_key}&content_type=files&response_format=json"
    data = session.get(url).json()

    return data["response"]["folder_content"].get("files", [])


def get_subfolders(folder_key):

    url = f"https://www.mediafire.com/api/1.5/folder/get_content.php?folder_key={folder_key}&content_type=folders&response_format=json"
    data = session.get(url).json()

    return data["response"]["folder_content"].get("folders", [])


def crawl_folder(folder_key, base_path, jobs):

    files = get_files(folder_key)

    for f in files:
        jobs.append((f["links"]["normal_download"], base_path))

    folders = get_subfolders(folder_key)

    for folder in folders:
        subname = folder["name"]
        new_path = os.path.join(base_path, subname)
        crawl_folder(folder["folderkey"], new_path, jobs)


def download_single_file(url):
    download_file(url, DOWNLOAD_ROOT)


def main():

    url = input("Paste MediaFire URL: ").strip()

    os.makedirs(DOWNLOAD_ROOT, exist_ok=True)

    if "/file/" in url:
        download_single_file(url)
        return

    folder_key = get_folder_key(url)

    if not folder_key:
        print("Invalid MediaFire link")
        return

    jobs = []

    crawl_folder(folder_key, DOWNLOAD_ROOT, jobs)

    print(f"\nFound {len(jobs)} files\n")

    with ThreadPoolExecutor(MAX_WORKERS) as pool:
        for job in jobs:
            pool.submit(download_file, job[0], job[1])


if __name__ == "__main__":
    main()
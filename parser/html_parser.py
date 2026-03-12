import os
from bs4 import BeautifulSoup


def extract_usernames_from_html(path):

    usernames = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        links = soup.find_all("a")

        for link in links:
            text = link.get_text(strip=True)
            if text and "instagram.com" not in text.lower():
                usernames.append(text)

    except Exception:
        pass

    return usernames


def find_html_files_recursive(folder, keyword):
    """
    Recursively find HTML files containing keyword in filename.
    Instagram exports nest files inside subdirectories.
    """
    files = []

    for root, dirs, filenames in os.walk(folder):
        for f in filenames:
            if keyword in f.lower() and f.endswith(".html"):
                files.append(os.path.join(root, f))

    return files


def parse_html_export(folder):

    followers = []
    following = []

    follower_files = find_html_files_recursive(folder, "followers")
    following_files = find_html_files_recursive(folder, "following")

    for file in follower_files:
        followers.extend(extract_usernames_from_html(file))

    for file in following_files:
        following.extend(extract_usernames_from_html(file))

    return {
        "followers": list(set(followers)),
        "following": list(set(following)),
        "likes": [],
        "comments": []
    }
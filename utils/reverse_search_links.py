def reverse_search_urls(image_path):
    """
    Returns reverse image search upload page links.
    These services do not accept local file paths as URLs;
    the links open each service's upload interface so the user
    can submit the downloaded file manually.
    """
    return {
        "google_lens": "https://lens.google.com/",
        "bing":        "https://www.bing.com/visualsearch",
        "yandex":      "https://yandex.com/images/search?rpt=imageview",
        "tineye":      "https://tineye.com/",
    }
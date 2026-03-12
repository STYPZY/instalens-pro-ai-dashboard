import urllib.parse


def reverse_search_urls(image_path):

    encoded = urllib.parse.quote(image_path)

    return {
        "google_lens": f"https://lens.google.com/uploadbyurl?url={encoded}",
        "bing": f"https://www.bing.com/images/search?q=imgurl:{encoded}",
        "yandex": f"https://yandex.com/images/search?rpt=imageview&url={encoded}"
    }
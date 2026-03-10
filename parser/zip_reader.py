
import zipfile, json, io

def read_instagram_zip(file):
    data={}
    with zipfile.ZipFile(file) as z:
        for name in z.namelist():
            if name.endswith(".json"):
                try:
                    with z.open(name) as f:
                        data[name]=json.load(io.TextIOWrapper(f,"utf-8"))
                except:
                    pass
    return data

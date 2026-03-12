from hachoir.parser import createParser
from hachoir.metadata import extractMetadata


def extract_metadata(path):

    metadata_data = {}

    try:

        parser = createParser(path)

        if not parser:
            return metadata_data

        metadata = extractMetadata(parser)

        if not metadata:
            return metadata_data

        for item in metadata.exportPlaintext():

            if ":" in item:

                key, value = item.split(":", 1)
                metadata_data[key.strip()] = value.strip()

    except Exception:
        pass

    return metadata_data
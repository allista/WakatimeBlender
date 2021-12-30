import sys


def u(text):
    if text is None:
        return None
    if isinstance(text, bytes):
        try:
            return text.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return text.decode(sys.getdefaultencoding())
            except UnicodeDecodeError:
                pass
    try:
        return str(text)
    except Exception:
        return text

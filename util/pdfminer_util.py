import re

def fix_pdfminer_cid(text):
    def sub_cid(match):
        val = int(match.group(1))
        return chr(val) if val < 128 else "!"
    text = re.sub(r"\(cid:(\d+?)\)",
        sub_cid, text)
    return text

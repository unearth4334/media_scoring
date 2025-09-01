"""PNG metadata parsing utilities"""
import zlib
from pathlib import Path
from typing import Optional


def read_png_parameters_text(png_path: Path, max_bytes: int = 2_000_000) -> Optional[str]:
    """
    Best-effort parse of PNG tEXt/zTXt/iTXt chunks to extract a 'parameters' text blob
    (e.g., Automatic1111 / ComfyUI). Returns the text payload if found; otherwise None.
    """
    try:
        with open(png_path, "rb") as f:
            sig = f.read(8)
            if sig != b"\x89PNG\r\n\x1a\n":
                return None
            read_total = 8
            param_text = None
            while True:
                if read_total > max_bytes:
                    break
                len_bytes = f.read(4)
                if len(len_bytes) < 4:
                    break
                length = int.from_bytes(len_bytes, "big")
                ctype = f.read(4)
                if len(ctype) < 4:
                    break
                data = f.read(length)
                if len(data) < length:
                    break
                _crc = f.read(4)
                read_total += 12 + length
                if ctype in (b"tEXt", b"zTXt", b"iTXt"):
                    try:
                        if ctype == b"tEXt":
                            # keyword\0text
                            if b"\x00" in data:
                                keyword, text = data.split(b"\x00", 1)
                                key = keyword.decode("latin-1", "ignore").strip().lower()
                                if key in ("parameters", "comment", "description"):
                                    t = text.decode("utf-8", "ignore").strip()
                                    if t:
                                        param_text = t
                        elif ctype == b"zTXt":
                            # keyword\0compression_method\0 compressed_text
                            if b"\x00" in data:
                                parts = data.split(b"\x00", 2)
                                if len(parts) >= 3:
                                    keyword = parts[0].decode("latin-1", "ignore").strip().lower()
                                    comp_method = parts[1][:1] if parts[1] else b"\x00"
                                    comp_data = parts[2]
                                    if comp_method == b"\x00":  # zlib/deflate
                                        try:
                                            txt = zlib.decompress(comp_data).decode("utf-8", "ignore").strip()
                                            if keyword in ("parameters", "comment", "description") and txt:
                                                param_text = txt
                                        except Exception:
                                            pass
                        elif ctype == b"iTXt":
                            # keyword\0 compression_flag\0 compression_method\0 language_tag\0 translated_keyword\0 text
                            # We handle only uncompressed (compression_flag==0)
                            parts = data.split(b'\x00', 5)
                            if len(parts) >= 6:
                                keyword = parts[0].decode("utf-8", "ignore").strip().lower()
                                comp_flag = parts[1][:1] if parts[1] else b"\x00"
                                # parts[2]=comp_method, parts[3]=language_tag, parts[4]=translated_keyword
                                text = parts[5]
                                if comp_flag == b"\x00":
                                    t = text.decode("utf-8", "ignore").strip()
                                    if keyword in ("parameters", "comment", "description") and t:
                                        param_text = t
                    except Exception:
                        pass
                if ctype == b"IEND":
                    break
            return param_text
    except Exception:
        return None
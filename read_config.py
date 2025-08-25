#!/usr/bin/env python3
import argparse, sys, os, json
try:
    import yaml  # type: ignore
except Exception as e:
    print("ERROR: PyYAML not installed. Please run: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(2)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', default='config.yml')
    ap.add_argument('--format', choices=['sh','ps','bat','json'], default='json')
    args = ap.parse_args()
    cfg = {}
    if os.path.exists(args.file):
        with open(args.file, 'r', encoding='utf-8') as f:
            try: cfg = yaml.safe_load(f) or {}
            except Exception as e:
                print(f'ERROR: failed to parse {args.file}: {e}', file=sys.stderr); sys.exit(3)
    dir_ = cfg.get('dir') or cfg.get('directory') or os.getcwd()
    port = int(cfg.get('port', 7862)); host = cfg.get('host', '127.0.0.1')
    style = cfg.get('style', 'style_default.css')
    generate_thumbnails = bool(cfg.get('generate_thumbnails', False))
    thumbnail_height = int(cfg.get('thumbnail_height', 64))
    if args.format == 'json':
        print(json.dumps({'dir': dir_, 'port': port, 'host': host, 'style': style, 'generate_thumbnails': generate_thumbnails, 'thumbnail_height': thumbnail_height})); return
    if args.format == 'sh':
        print(f'DIR={json.dumps(dir_)}'); print(f'PORT={port}'); print(f'HOST={json.dumps(host)}'); print(f'STYLE={json.dumps(style)}'); print(f'GENERATE_THUMBNAILS={json.dumps(generate_thumbnails)}'); print(f'THUMBNAIL_HEIGHT={thumbnail_height}'); return
    if args.format == 'ps':
        print(f'$Dir = {json.dumps(dir_)}'); print(f'$Port = {port}'); print(f'$Host = {json.dumps(host)}'); print(f'$Style = {json.dumps(style)}'); print(f'$GenerateThumbnails = {json.dumps(generate_thumbnails)}'); print(f'$ThumbnailHeight = {thumbnail_height}'); return
    if args.format == 'bat':
        esc_dir = dir_.replace('%','%%'); esc_host = host.replace('%','%%'); esc_style = style.replace('%','%%')
        print(f'set "DIR={esc_dir}"'); print(f'set "PORT={port}"'); print(f'set "HOST={esc_host}"'); print(f'set "STYLE={esc_style}"'); print(f'set "GENERATE_THUMBNAILS={generate_thumbnails}"'); print(f'set "THUMBNAIL_HEIGHT={thumbnail_height}"'); return
if __name__ == '__main__': main()

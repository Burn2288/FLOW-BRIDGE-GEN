"""Portable explicit UTF-8 KEY=value configuration. No shell evaluation."""
import os,re
from pathlib import Path

def parse_env_file(path):
    path=Path(path).expanduser().resolve()
    if path.stat().st_size>1024*1024:raise ValueError('Configuration file too large')
    values={}
    for number,line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
        line=line.strip()
        if not line or line.startswith('#'):continue
        key,sep,value=line.partition('=');key=key.strip();value=value.strip()
        if not sep or not re.fullmatch(r'[A-Z][A-Z0-9_]*',key) or key in values:raise ValueError(f'Invalid configuration line {number}')
        if value.startswith(('"',"'")):
            if len(value)<2 or value[-1]!=value[0]:raise ValueError(f'Invalid configuration line {number}')
            value=value[1:-1]
        if any(ord(c)<32 for c in value):raise ValueError(f'Invalid configuration line {number}')
        values[key]=value
    return values

def load_env_file(path):
    # Exported environment has priority; no variable, command or escape expansion.
    for key,value in parse_env_file(path).items():os.environ.setdefault(key,value)
    return Path(path).expanduser().resolve().parent

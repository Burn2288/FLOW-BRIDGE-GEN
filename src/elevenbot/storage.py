from pathlib import Path
import hashlib,os,json,subprocess,uuid

class Storage:
    def __init__(self,root):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        os.chmod(self.root,0o700)
    def path(self,key):
        # Keys are generated internally, never external paths/URLs.
        if not isinstance(key,str) or '/' in key or '\\' in key or not key.endswith('.mp3'):raise ValueError('Bad storage key')
        parts=key[:-4].split('_')
        if len(parts)!=2:raise ValueError('Bad storage key')
        uuid.UUID(parts[0]);uuid.UUID(parts[1])
        p=self.root/key
        if p.is_symlink():raise ValueError('Symlink forbidden')
        return p
    def save(self,j,fence,data):
        if not 128<=len(data)<=20*1024*1024 or not(data[:3]==b'ID3' or data[0]==255 and data[1]&224==224):raise ValueError('Invalid MP3')
        key=f'{j}_{fence}.mp3';p=self.path(key);tmp=p.with_suffix('.tmp')
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            with os.fdopen(fd,'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
            result=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(tmp)],capture_output=True,timeout=10,check=True)
            duration=float(json.loads(result.stdout)['format']['duration'])
            if not 0<duration<=3600:raise ValueError('Invalid duration')
            os.replace(tmp,p)
            if os.name!='nt':
                d=os.open(self.root,os.O_RDONLY)
                try:os.fsync(d)
                finally:os.close(d)
        finally:
            tmp.unlink(missing_ok=True)
        return {'key':key,'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}

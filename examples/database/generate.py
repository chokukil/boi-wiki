"""Invented examples, generated from scratch; no production data or identities."""
import argparse
from pathlib import Path
import sqlite3


def generate(path, *, variant=1):
    path=Path(path)
    if path.exists():raise ValueError('Refusing to replace an existing database')
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE procedures (procedure_key TEXT PRIMARY KEY, purpose TEXT, checkpoint TEXT, condition TEXT)')
        db.execute('INSERT INTO procedures VALUES (?,?,?,?)', (f'RINSE-{variant}',
            '외부 덮개의 먼지를 제거한다.', '배출수의 탁도를 점검한다.', '덮개 온도가 35 C 미만일 때 수행한다.'))
        db.execute('CREATE TABLE telemetry (signal_key TEXT, equipment TEXT, role TEXT, unit TEXT, value REAL, range_note TEXT, lower_limit REAL, upper_limit REAL)')
        db.executemany('INSERT INTO telemetry VALUES (?,?,?,?,?,?,?,?)', [
            (f'M-{variant}',f'ORBIT-{variant}','측정값','kPa',82+variant,'설명 범위: 10~140 kPa',None,None),
            (f'S-{variant}',f'ORBIT-{variant}','설정값','kPa',80,'설정 범위: 20~120 kPa',20,120),
            (f'X-{variant}',f'ORBIT-{variant}','측정값','mA',None,'문서 A: -5~15 mA; 문서 B: 5~15 mA',None,None)])
        db.execute('CREATE TABLE components (component_key TEXT PRIMARY KEY, label TEXT)')
        db.executemany('INSERT INTO components VALUES (?,?)',[(f'C-{variant}','가상 냉각 모듈'),(f'U-{variant}','미연결 모듈')])
        db.execute('CREATE TABLE route_steps (component_key TEXT, procedure_key TEXT, position INTEGER)')
        db.executemany('INSERT INTO route_steps VALUES (?,?,?)',[(f'C-{variant}',f'RINSE-{variant}',1)]*2)
        db.execute('CREATE TABLE restricted_notes (text TEXT)')
        db.execute('INSERT INTO restricted_notes VALUES (?)',('허용 범위 밖의 합성 메모',))
    return path


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path',type=Path)
    parser.add_argument('--variant',type=int,default=1)
    args=parser.parse_args();generate(args.path,variant=args.variant)

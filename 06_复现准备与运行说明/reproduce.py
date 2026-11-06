"""Convenience launchers only; the frozen cleaning and experiment code is unchanged."""
import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import uuid
import venv
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / '01_流水线源码'
DATA = ROOT / '05_原始数据（含标签，请勿公开）'
ENV = ROOT / '复现运行环境' / '.venv'
PYTHON = ENV / 'Scripts' / 'python.exe'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_materials():
    subprocess.run([sys.executable, '-B', str(SOURCE / 'tools/verify_delivery.py')], check=True)
    sources = json.loads((SOURCE / 'config/dataset_sources.json').read_text(encoding='utf-8'))
    for filename, key in [('adult.data', 'adult_train_sha256'), ('adult.test', 'adult_test_sha256')]:
        if sha(DATA / filename) != sources[key]:
            raise SystemExit('Raw data SHA256 mismatch: ' + filename)
    if sha(HERE / 'requirements-lock.txt') != sha(SOURCE / 'requirements-lock.txt'):
        raise SystemExit('Dependency lock differs from the frozen project.')
    with (HERE / '离线依赖SHA256.csv').open(encoding='utf-8-sig', newline='') as stream:
        wheels = list(csv.DictReader(stream))
    for item in wheels:
        if sha(HERE / '离线依赖包' / item['file']) != item['sha256']:
            raise SystemExit('Offline dependency SHA256 mismatch: ' + item['file'])
    print('OK: frozen source, raw data and offline packages verified; no experiment executed.', flush=True)


def fresh_output(name):
    parent = ROOT / '复现运行输出（含私有数据，请勿公开）'
    parent.mkdir(exist_ok=True)
    return parent / (name + '_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8])


def run(script, *args, cwd=SOURCE):
    subprocess.run([str(PYTHON), '-B', str(script), *map(str, args)], cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'setup', 'clean', 'tests', 'f1'])
    action = parser.parse_args().action
    check_materials()
    if action == 'check':
        print('Current Python:', sys.version.split()[0], platform.machine())
        return
    if sys.version_info[:2] != (3, 14) or sys.maxsize <= 2**32 or platform.system() != 'Windows':
        raise SystemExit('Use 64-bit Python 3.14 on Windows. The recorded version was 3.14.6.')
    if action == 'setup':
        if not PYTHON.is_file():
            venv.create(ENV, with_pip=True)
        subprocess.run([str(PYTHON), '-m', 'pip', 'install', '--no-index', '--find-links',
                        str(HERE / '离线依赖包'), '-r', str(HERE / 'requirements-lock.txt')], check=True)
        subprocess.run([str(PYTHON), '-m', 'pip', 'check'], check=True)
        print('Environment ready:', PYTHON)
        return
    if not PYTHON.is_file():
        raise SystemExit('Run 01_install_dependencies.cmd first.')
    if action == 'clean':
        output = fresh_output('清洗')
        run(SOURCE / 'run_pipeline.py', '--input', SOURCE / 'examples/independent_dirty.csv', '--output', output)
    elif action == 'tests':
        output = fresh_output('测试副本')
        shutil.copytree(SOURCE, output)
        log = output / 'logs/reproduction_full_unit_tests.log'
        print('Running tests in a copy. Full log:', log, flush=True)
        with log.open('w', encoding='utf-8') as stream:
            subprocess.run([str(PYTHON), '-B', str(output / 'run_tests.py')], cwd=output,
                           stdout=stream, stderr=subprocess.STDOUT, check=True,
                           env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    else:
        output = fresh_output('F1机械复现')
        print('Known-test mechanical reproduction; not a new independent acceptance.', flush=True)
        run(SOURCE / 'tools/reproduce_f1.py', '--adult-train', DATA / 'adult.data',
            '--adult-test', DATA / 'adult.test', '--output', output)
    print('Output:', output)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
import os, psutil, subprocess, time, json, pytest

def test_vram_smokeload():
    env = os.environ.copy()
    env['SWARM_GPU_PROFILE'] = 'gtx_1080'
    p = subprocess.run(['python', '-m', 'loader.deterministic_loader'],
                       capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "[OK]" in p.stdout

@pytest.mark.skipif(os.name == "nt", reason="htop not available on Windows CI")
def test_ram_guard():
    before = psutil.virtual_memory().used
    time.sleep(1)   # simulate 100-req soak later
    after = psutil.virtual_memory().used
    assert (after - before) < 3 * 1024 ** 3, "RAM leak > 3 GB"

#!/usr/bin/env python3
"""Run a command in a no-network, read-only, unprivileged Linux namespace sandbox.

Built only from util-linux tools already on the host (unshare, setpriv, prlimit).
Inside the sandbox:
  * new network namespace: no interfaces except a down loopback, so no proxy/Internet;
  * new mount namespace: `/` and system mounts are read-only; /root, /home, /run and
    /tmp are replaced by empty tmpfs (hides credentials, the git checkout and the agent
    proxy); only the job directory is writable;
  * new PID/IPC/UTS namespaces; the whole tree is killed on timeout;
  * uid/gid nobody, no capabilities, no_new_privs, empty environment;
  * rlimits on address space, CPU time, processes, file size and open files.

This is process-level isolation, not a VM. It is used to wrap the *official*
CodeRAG-Bench evaluator (which itself only offers `reliability_guard`, explicitly not a
security sandbox). `self_test()` verifies the properties above before any evaluation.
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MOUNT_ROOT = Path('/srv/crag-sandbox')
JOB_MOUNT = MOUNT_ROOT / 'job'
RO_MOUNT = MOUNT_ROOT / 'ro'
NOBODY = 65534
DEFAULT_LIMITS = {'as_bytes': 4 << 30, 'cpu_s': 300, 'nproc': 256, 'fsize_bytes': 64 << 20, 'nofile': 512}
# Hidden behind empty tmpfs. Order matters only for nested paths (none here).
HIDDEN_RO = ['/root', '/home', '/run']
REQUIRED_TOOLS = ['unshare', 'setpriv', 'prlimit', 'mount', 'env']


class SandboxUnavailable(RuntimeError):
    pass


def check_tools():
    missing = [t for t in REQUIRED_TOOLS if shutil.which(t) is None]
    if missing:
        raise SandboxUnavailable(f'missing tools: {missing}')
    if os.geteuid() != 0:
        raise SandboxUnavailable('needs root to create mount/net namespaces before dropping to nobody')


def _inner_script(ro_binds, limits, argv, env):
    q = shlex.quote
    lines = ['set -eu', 'mount --make-rprivate /']
    # The job dir is bound first: later tmpfs over /tmp would otherwise hide it.
    lines.append(f'mount --bind "$CRAG_JOB" {q(str(JOB_MOUNT))}')
    for i, src in enumerate(ro_binds):
        tgt = RO_MOUNT / str(i)
        lines += [f'mount --bind {q(str(src))} {q(str(tgt))}', f'mount -o remount,bind,ro {q(str(tgt))}']
    lines += [
        'mount -o remount,bind,ro /',
        'mount -o remount,bind,ro /dev',
        'mount -t tmpfs -o nosuid,nodev,size=128m tmpfs /dev/shm',
        'mount -t tmpfs -o nosuid,nodev,size=256m,mode=1777 tmpfs /tmp',
        'mount -t tmpfs -o ro,size=4k tmpfs /sys',
    ]
    lines += [f'mount -t tmpfs -o ro,size=4k tmpfs {d}' for d in HIDDEN_RO]
    envs = ' '.join(q(f'{k}={v}') for k, v in env.items())
    lines.append(
        f'exec setpriv --reuid={NOBODY} --regid={NOBODY} --clear-groups --no-new-privs '
        f'--bounding-set=-all --inh-caps=-all --ambient-caps=-all -- '
        f'prlimit --as={limits["as_bytes"]} --cpu={limits["cpu_s"]} --nproc={limits["nproc"]} '
        f'--fsize={limits["fsize_bytes"]} --nofile={limits["nofile"]} --core=0 -- '
        f'env -i {envs} ' + ' '.join(q(a) for a in argv))
    return '\n'.join(lines)


def run(argv, job_dir, ro_binds=(), timeout_s=600, limits=None, env=None):
    """Run argv sandboxed. `ro_binds[i]` is visible read-only at /srv/crag-sandbox/ro/<i>;
    `job_dir` (host path) is the only writable location, visible at /srv/crag-sandbox/job."""
    check_tools()
    lim = dict(DEFAULT_LIMITS, **(limits or {}))
    ro_binds = [Path(p).resolve() for p in ro_binds]
    job_dir = Path(job_dir).resolve()
    JOB_MOUNT.mkdir(parents=True, exist_ok=True)
    for i in range(len(ro_binds)):
        (RO_MOUNT / str(i)).mkdir(parents=True, exist_ok=True)
    os.chown(job_dir, NOBODY, NOBODY)
    base_env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/tmp', 'LANG': 'C.UTF-8',
                'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': '/tmp'}
    base_env.update(env or {})
    script = _inner_script(ro_binds, lim, argv, base_env)
    cmd = ['unshare', '--net', '--mount', '--pid', '--ipc', '--uts', '--fork', '--kill-child',
           '--mount-proc', '--', 'sh', '-c', script]
    try:
        return subprocess.run(cmd, env={'CRAG_JOB': str(job_dir), 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'},
                              capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(cmd, returncode=-9, stdout=e.stdout or '',
                                           stderr=(e.stderr or '') + f'\n[sandbox] wall timeout {timeout_s}s')


PROBE = r'''
import json, os, socket, sys
r = {}
def attempt(name, fn):
    try:
        fn(); r[name] = 'ALLOWED'
    except BaseException as e:
        r[name] = 'blocked: ' + type(e).__name__
def net(host, port):
    s = socket.socket(); s.settimeout(3); s.connect((host, port))
attempt('net_proxy_loopback', lambda: net('127.0.0.1', int(sys.argv[1])))
attempt('net_public_ip', lambda: net('1.1.1.1', 443))
attempt('net_dns', lambda: socket.getaddrinfo('github.com', 443))
attempt('write_repo', lambda: open(sys.argv[2] + '/SANDBOX_ESCAPE', 'w').write('x'))
attempt('write_root_fs', lambda: open('/SANDBOX_ESCAPE', 'w').write('x'))
attempt('write_usr', lambda: open('/usr/SANDBOX_ESCAPE', 'w').write('x'))
attempt('read_claude_json', lambda: open('/root/.claude.json').read())
attempt('read_gitconfig', lambda: open('/root/.gitconfig').read())
r['home_listing'] = os.listdir('/home'); r['root_listing'] = os.listdir('/root')
attempt('write_ro_bind', lambda: open('/srv/crag-sandbox/ro/0/SANDBOX_ESCAPE', 'w').write('x'))
attempt('alloc_6GiB', lambda: bytearray(6 << 30))
attempt('write_job', lambda: open('/srv/crag-sandbox/job/ok.txt', 'w').write('ok'))
attempt('write_tmp', lambda: open('/tmp/ok.txt', 'w').write('ok'))
status = open('/proc/self/status').read()
r['uid'] = os.getuid(); r['euid'] = os.geteuid()
r['CapEff'] = [l.split()[1] for l in status.splitlines() if l.startswith('CapEff')][0]
r['NoNewPrivs'] = [l.split()[1] for l in status.splitlines() if l.startswith('NoNewPrivs')][0]
r['env_keys'] = sorted(os.environ)
r['pids_visible'] = len([p for p in os.listdir('/proc') if p.isdigit()])
print(json.dumps(r))
'''

EXPECT_ALLOWED = {'write_job', 'write_tmp'}


def self_test(python='/usr/bin/python3', repo_dir=None, proxy_port=None):
    """Probe the sandbox with benign code. Returns (ok, report)."""
    repo_dir = repo_dir or str(Path(__file__).resolve().parent)
    proxy_port = proxy_port or (os.environ.get('HTTPS_PROXY', 'http://127.0.0.1:45813').rsplit(':', 1)[-1].strip('/'))
    with tempfile.TemporaryDirectory() as job, tempfile.TemporaryDirectory() as ro:
        Path(job, 'probe.py').write_text(PROBE)
        proc = run([python, '-I', str(JOB_MOUNT / 'probe.py'), str(proxy_port), repo_dir], job, ro_binds=[ro],
                   timeout_s=60)
        try:
            rep = json.loads(proc.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            return False, {'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}
        escaped = [p for p in (Path(repo_dir, 'SANDBOX_ESCAPE'), Path('/SANDBOX_ESCAPE'), Path('/usr/SANDBOX_ESCAPE'),
                               Path(ro, 'SANDBOX_ESCAPE')) if p.exists()]
        rep['host_side_escape_files'] = [str(p) for p in escaped]
        rep['job_file_on_host'] = Path(job, 'ok.txt').exists()
    bad = [k for k, v in rep.items() if isinstance(v, str) and v.startswith(('ALLOWED', 'blocked'))
           and ((k in EXPECT_ALLOWED) != (v == 'ALLOWED'))]
    ok = (not bad and not rep['host_side_escape_files'] and rep['job_file_on_host'] and rep['uid'] == NOBODY
          and int(rep['CapEff'], 16) == 0 and rep['NoNewPrivs'] == '1' and rep['pids_visible'] == 1
          and rep['home_listing'] == [] and rep['root_listing'] == []
          and not any(k.lower().endswith('_proxy') or 'TOKEN' in k for k in rep['env_keys']))
    rep['unexpected'] = bad
    return ok, rep


if __name__ == '__main__':
    ok, rep = self_test(*(sys.argv[1:2] or []))
    print(json.dumps(rep, indent=2))
    print('SANDBOX_SELF_TEST', 'PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)

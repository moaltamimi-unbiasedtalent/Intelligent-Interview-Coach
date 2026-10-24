"""Optional Redis profiles preserve the immutable application image boundary."""
import copy
from pathlib import Path

import pytest
import yaml

from scripts import release_redis as R

ROOT = Path(__file__).resolve().parents[1]


def base():
    profile = yaml.safe_load((ROOT / 'deploy/docker-compose.staging.yml').read_text())
    for name in ('api','worker','migrate','web'):
        profile['services'][name].pop('build')
        profile['services'][name]['image'] = 'sha256:' + ('a' if name != 'web' else 'b') * 64
        profile['services'][name]['pull_policy'] = 'never'
    return profile


@pytest.mark.parametrize('topology', ['internal','managed'])
def test_optional_topologies_preserve_images_migrations_volumes_and_nonactivation(tmp_path, topology):
    original = base()
    snapshot = copy.deepcopy(original)
    profile = R.apply(original, ROOT, tmp_path, topology=topology, namespace='ask4mo:rl:staging:v1:',
                      password_file='/runtime/redis-password' if topology == 'internal' else None)
    assert original == snapshot
    for name in ('api','worker','migrate','web'):
        assert profile['services'][name]['image'] == original['services'][name]['image']
        assert profile['services'][name]['pull_policy'] == 'never'
    for name in ('api','worker'):
        service = profile['services'][name]
        assert service['depends_on']['migrate'] == {'condition':'service_completed_successfully'}
        assert service['volumes'] == original['services'][name]['volumes']
        assert service['environment']['RATE_LIMIT_SHARED_REQUIRED'] == 'true'
        assert service['environment']['RATE_LIMIT_NAMESPACE'] == 'ask4mo:rl:staging:v1:'
    assert profile['services']['migrate']['command'] == ['bash','scripts/migrate.sh']
    assert profile['services']['migrate']['restart'] == 'no'
    assert 'RATE_LIMIT_KEY_SECRET' not in yaml.safe_dump(profile)
    if topology == 'internal':
        service = profile['services']['redis']
        assert '@sha256:' in service['image'] and 'ports' not in service
        assert service['user'] == '999:1000' and service['read_only']
        assert service['cap_drop'] == ['ALL']
        assert profile['networks']['rate-limit-store']['internal']
        assert profile['secrets']['redis_password']['file'] == '/runtime/redis-password'
    else:
        assert 'redis' not in profile['services'] and 'secrets' not in profile


@pytest.mark.parametrize('options', [dict(topology='internal'), dict(namespace='unused'), dict(topology='managed',namespace='invalid'),
    dict(topology='internal',namespace='ask4mo:rl:staging:v1:',password_file='relative'),
    dict(topology='managed',namespace='ask4mo:rl:staging:v1:',password_file='/private/file')])
def test_incomplete_or_conflicting_redis_plan_refuses(tmp_path, options):
    with pytest.raises(ValueError, match='redis_release_configuration_refused'):
        R.apply(base(),ROOT,tmp_path,**options)


def test_no_selected_topology_keeps_the_existing_profile():
    original=base()
    assert R.apply(original,ROOT,'/unused') is original

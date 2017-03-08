import logging
import re
import hashlib
from django.core.cache import cache
from django.utils.encoding import smart_str

log = logging.getLogger(__name__)

# The new API is simply:
#
#   - version()
#   - get()
#   - incr()
#
# usage example:
#
#    getting a single thing from the account namespace:
#
#        my_segment = get(
#            version('segment-' + my_segment.code, account),
#            lambda: account.segments.all().order_by('name'))
#
#    getting a list of things from the account namespace:
#
#        all_segments = get(
#            version('segments', account) + '.all',
#            lambda: account.segments.all().order_by('name'))
#
#    getting a single thing from the global namespace:
#
#        account = get(
#            version('account-' + account_code),
#            lambda: Account.objects.get(code=account_code))
#
#    invalidating things in the account namespace:
#
#        def invalidate_cache(self):
#            incr('segments', self.account)
#            incr('segment-' + self.id, self.account)

VERSION_SUFFIX = '.version'

def safe_cache_key(key, no_limit=False):
    """Returns a safe cache key (esp. for memcache which has restrictions on what keys are valid).

    Replaces invalid memcache control characters with an underscore. If len is > 240 will return part
    of the value plus an md5 hexdigest of value.

    (set to 230 and not 250 to make room for prefix and suffix)
    """
    # force to bytestring to make any unicode safe for memcached
    cache_key = smart_str(key, encoding='ascii', errors='ignore')
    if len(cache_key) > 230:
        if not no_limit:
            # use a subset of data to form the cache key
            cache_key = cache_key[:197] + '-' + hashlib.md5(cache_key[:500]).hexdigest()  # adds up to len 230
        else:
            cache_key = hashlib.md5(cache_key).hexdigest()

    # remove any characters not between ascii 33 and 127 for memcached
    cache_key = re.sub(r'[^\u0021-\u007F]', '-', cache_key, re.UNICODE)
    return cache_key


def get_version(key):
    """Get a version number from the cache, or create one if it doesn't exist."""
    version_key = safe_cache_key(key) + VERSION_SUFFIX
    version = cache.get(version_key)
    if not version:
        log.debug('CACHE: Creating new version key %s' % version_key)
        cache.set(version_key, 1, None)  # doesn't expire
        version = 1
    return version


def version(key):
    """Generate a key with the latest version number from the cache."""
    return '%s:%s' % (safe_cache_key(key), get_version(key))


def getf(key, f, ttl=60*60*23):
    """Get an item from the cache, or update it if it's not there, default to 48 hour TTL. Return the item
    and a refreshed flag.
    """
    safe_key = safe_cache_key(key)
    item = cache.get(safe_key)
    if item is None:  # specifically checking against None, so 0, [], etc get through
        item = f()
        cache.set(safe_key, item, ttl)
        refreshed = True
        log.debug('CACHE: Adding item to cache at %s' % (safe_key, ))
    else:
        refreshed = False
        log.debug('CACHE: Found cached item at %s' % safe_key)
    return item, refreshed


def get(key, f, ttl=60 * 60 * 23):
    """Get an item from the cache, or update it if it's not there, default to 48 hour TTL. Return the item."""
    item, refreshed = getf(key, f, ttl=ttl)
    return item

def incr(key):
    """Increment the version of an item, or create one if it doesn't exist."""
    version_key = safe_cache_key(key) + VERSION_SUFFIX
    try:
        cache.incr(version_key)
        log.debug('CACHE: Increment version key %s' % version_key)
    except ValueError:
        cache.add(version_key, 1)
        log.debug('CACHE: Create version key %s' % version_key)

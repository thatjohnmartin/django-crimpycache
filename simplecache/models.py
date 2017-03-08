import logging
from django.db import models
from . import cache

log = logging.getLogger(__name__)


class CacheMixin(models.Model):
    """A mixin to make it easy to cache ORM objects."""

    class Meta:
        abstract = True

    cache_key_fields = ('id',)
    cache_key_fields_lookup = {}
    cache_key_all = 'all'

    def __init__(self, *args, **kwargs):
        super(CacheMixin, self).__init__(*args, **kwargs)

    @classmethod
    def generate_cache_key_dict_key(cls, key):
        """Turns any type of key (within reason) to a sorted tuple."""
        if type(key) == str:
            return (key,)
        else:
            return tuple(sorted(key))

    @classmethod
    def generate_cache_key_from_fields(cls, ordered_field_names, values):
        """Generate a cache key from a tuple of field names and a dict of values or ORM object."""
        cache_key = ""
        is_dict = type(values) == dict
        for field in ordered_field_names:
            cache_key += '-%s-%s' % (field, str(values[field] if is_dict else getattr(values, field)))
        return cls._meta.db_table + cache_key

    @classmethod
    def generate_cache_key_from_label(cls, label):
        """Generate a cache key from a label, useful for arbitrary lists."""
        return cls._meta.db_table + '-' + label

    @classmethod
    def get_from_cache(cls, **kwargs):
        """Get a single item from the cache, or populate the cache if it doesn't exist."""
        key = cls.generate_cache_key_dict_key(kwargs.keys())
        assert key in cls.cache_key_fields_lookup, 'The cache argument(s) "%s" were not declared' % key
        # TODO: we could cache by each key, not just the given one, cache.get take another param
        # TODO: notice foreign key fields and resolve to <name>_id, maybe accept both forms for single cache
        return cache.get(
            cache.version(cls.generate_cache_key_from_fields(cls.cache_key_fields_lookup[key], kwargs)),
            lambda: cls.objects.get(**kwargs))

    @classmethod
    def all_from_cache(cls):
        """Get a list of all objects from the cache, or populate the cache if that list doesn't exist."""
        # TODO: we could cache each individual object here
        return cache.get(
            cache.version(cls.generate_cache_key_from_label(cls.cache_key_all)),
            lambda: cls.objects.all())


def invalidate_cache(sender, instance, **kwargs):
    """Invalidate all of the known cache keys."""

    if issubclass(sender, CacheMixin):
        # invalidate all key fields
        for key in sender.cache_key_fields:
            if type(key) == str:
                key = (key,)
            log.debug('CACHE: Invalidating %s for %s' % (key, instance))
            cache.incr(sender.generate_cache_key_from_fields(key, instance))

        # invalidate "all" list
        log.debug('CACHE: Invalidating %s for %s' % (sender.cache_key_all, instance))
        cache.incr(sender.generate_cache_key_from_label(sender.cache_key_all))

models.signals.post_save.connect(invalidate_cache)
models.signals.post_delete.connect(invalidate_cache)


def prepare_cache_keys_lookup(sender, **kwargs):
    """Creates a lookup for cache keys."""

    if issubclass(sender, CacheMixin):
        # create a dictionary of cache keys keyed by set
        for key in sender.cache_key_fields:
            if type(key) == str:
                key = (key,)
            sender.cache_key_fields_lookup[sender.generate_cache_key_dict_key(key)] = key

models.signals.class_prepared.connect(prepare_cache_keys_lookup)

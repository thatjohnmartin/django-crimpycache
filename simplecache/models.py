import logging
from django.db import models
from . import cache

log = logging.getLogger(__name__)

class CacheManager(object):

    _cache_key_fields_lookup = {}

    def __init__(self, model_class):
        self.model_class = model_class

        # create a dictionary of cache keys keyed by set
        for key in self.model_class.cache_key_fields:
            if type(key) == str:
                key = (key,)
            self._cache_key_fields_lookup[self._generate_cache_key_dict_key(key)] = key

    @staticmethod
    def _generate_cache_key_dict_key(key):
        """Turns any type of key (within reason) to a sorted tuple."""
        if type(key) == str:
            return (key,)
        else:
            return tuple(sorted(key))

    def _generate_cache_key_from_fields(self, ordered_field_names, values):
        """Generate a cache key from a tuple of field names and a dict of values or ORM object."""
        cache_key = ""
        is_dict = type(values) == dict
        for field in ordered_field_names:
            cache_key += '-%s-%s' % (field, str(values[field] if is_dict else getattr(values, field)))
        return self.model_class._meta.db_table + cache_key

    def _generate_cache_key_from_partition(self, partition, value):
        """Generate a cache key from a partition name and value, useful for caching groups of things."""
        return '%s-%s-%s' % (self.model_class._meta.db_table, partition, value)

    def _generate_cache_key_from_label(self, label):
        """Generate a cache key from a label, useful for arbitrary lists."""
        return self.model_class._meta.db_table + '-' + label

    def get_version_for_fields(self, key, values):
        return cache.version(self._generate_cache_key_from_fields(self._cache_key_fields_lookup[self._generate_cache_key_dict_key(key)], values))

    def get_version_for_partition(self, partition, value):
        return cache.version(self._generate_cache_key_from_partition(partition, value))

    def get_version_for_all(self):
        return cache.version(self._generate_cache_key_from_label(self.model_class.cache_key_all))

    def get(self, **kwargs):
        """Get a single item from the cache, or populate the cache if it doesn't exist. Return just the item."""
        item, refreshed = self.getf(**kwargs)
        return item

    def getf(self, **kwargs):
        """Get a single item from the cache, or populate the cache if it doesn't exist. Return the item and a
        refreshed flag."""
        key = self._generate_cache_key_dict_key(kwargs.keys())
        assert key in self._cache_key_fields_lookup, 'The cache argument(s) "%s" were not declared' % key
        # TODO: we could cache by each key, not just the given one, cache.get take another param
        # TODO: notice foreign key fields and resolve to <name>_id, maybe accept both forms for single cache
        return cache.getf(
            self.get_version_for_fields(self._cache_key_fields_lookup[key], kwargs),
            lambda: self.model_class.objects.get(**kwargs))

    def partition(self, partition, value):
        items, refreshed = self.partitionf(partition, value)
        return items

    def partitionf(self, partition, value):
        assert partition in self.model_class.cache_key_partitions, 'The partition %s was not declared' % partition
        return cache.getf(
            self.get_version_for_partition(partition, value),
            lambda: self.model_class.objects.filter(**{partition: value}))

    def all(self):
        """Get a list of all objects from the cache, or populate the cache if that list doesn't exist."""
        items, refreshed = self.allf()
        return items

    def allf(self):
        """Get a list of all objects from the cache, or populate the cache if that list doesn't exist. Return the
        list of items and a refreshed flag.
        """
        # TODO: we could cache each individual object here
        return cache.getf(
            self.get_version_for_all(),
            lambda: self.model_class.objects.all())


class CacheMixin(models.Model):
    """A mixin to make it easy to cache ORM objects."""

    class Meta:
        abstract = True

    cache_key_fields = ('id',)
    cache_key_partitions = ()
    cache_key_all = 'all'

    _cache_managers_by_type = {}


def invalidate_cache(sender, instance, **kwargs):
    """Invalidate all of the known cache keys."""

    if issubclass(sender, CacheMixin):
        # invalidate all key fields
        for key in sender.cache_key_fields:
            if type(key) == str:
                key = (key,)
            log.debug('CACHE: Invalidating field %s for %s' % (key, instance))
            cache.incr(sender.cache._generate_cache_key_from_fields(key, instance))

        # invalidate all partition fields
        for partition in sender.cache_key_partitions:
            log.debug('CACHE: Invalidating partition %s for %s' % (partition, instance))
            cache.incr(sender.cache._generate_cache_key_from_partition(partition, getattr(instance, partition)))

        # invalidate "all" list
        log.debug('CACHE: Invalidating %s for %s' % (sender.cache_key_all, instance))
        cache.incr(sender.cache._generate_cache_key_from_label(sender.cache_key_all))

models.signals.post_save.connect(invalidate_cache)
models.signals.post_delete.connect(invalidate_cache)


def init_cache_property(sender, **kwargs):
    """Initializes the cache manager class property."""
    if issubclass(sender, CacheMixin):
        if not sender in CacheMixin._cache_managers_by_type:
            CacheMixin._cache_managers_by_type[sender] = CacheManager(sender)
        setattr(sender, 'cache', CacheMixin._cache_managers_by_type[sender])


models.signals.class_prepared.connect(init_cache_property)

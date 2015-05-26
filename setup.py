from setuptools import setup, find_packages
from simplecache import __version__

setup(
    name='django-simplecache',
    version=__version__,
    author='John Martin',
    author_email='john@lonepixel.com',
    packages=find_packages(),
    url='https://github.com/thatjohnmartin/simplecache',
    license='MIT',
    install_requires=['Django>=1.8'],
    long_description=open('README.md').read(),
)
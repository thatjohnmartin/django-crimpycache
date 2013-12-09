from setuptools import setup, find_packages
from crimpycache import __version__

setup(
    name='django-crimpycache',
    version=__version__,
    author='John Martin',
    author_email='john@lonepixel.com',
    packages=find_packages(),
    url='https://github.com/johnmartin78/crimpycache',
    license='MIT',
    install_requires=['Django>=1.6'],
    long_description=open('README.md').read(),
)
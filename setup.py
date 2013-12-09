from distutils.core import setup
from crimpycache import __version__, __author__

setup(
    name='crimpycache',
    version=__version__,
    author=__author__,
    packages=['crimpycache',],
    url='https://github.com/johnmartin78/crimpycache',
    license='MIT',
    install_requires=['Django>=1.6'],
    long_description=open('README.md').read(),
)
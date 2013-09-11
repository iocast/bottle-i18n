#!/usr/bin/env python

from distutils.core import setup

try:
    from distutils.command.build_py import build_py_2to3 as build_py
except ImportError:
    from distutils.command.build_py import build_py

setup(
      name = 'bottle-i18n',
      version = '0.1',
      description = 'I18N integration for Bottle.',
      author = 'iocast',
      author_email = 'iocast@me.com',
      url = 'http://www.github.com/iocast/bottle-i18n',
      license = 'MIT',
      platforms = 'any',
      py_modules = [
                    'bottle_i18n'
                    ],
      requires = [
                  'bottle (>=0.11.6)'
                  ],
      classifiers = [
                     'Development Status :: 4 - Beta',
                     'Environment :: Web Environment',
                     'Intended Audience :: Developers',
                     'License :: OSI Approved :: MIT License',
                     'Operating System :: OS Independent',
                     'Programming Language :: Python',
                     'Programming Language :: Python :: 3',
                     'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
                     'Topic :: Software Development :: Libraries :: Python Modules'
                     ],
      cmdclass = {'build_py': build_py}
      )
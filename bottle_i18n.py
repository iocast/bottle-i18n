# -*- coding: utf-8 -*-
#

import functools
import gettext
import os
import sys

from bottle import (
    DictMixin,
    PluginError,
    request,
    template,
)

def i18n_defaults(template, request):
    template.defaults['_'] = lambda msgid, options=None: request.app._(msgid) % options if options else request.app._(msgid)
    template.defaults['lang'] = lambda: request.app.lang

def i18n_template(*args, **kwargs):
    tpl = args[0] if args else None
    if tpl:
        tpl = os.path.join("{lang!s}/".format(lang=request.app.lang), tpl)
    eles = list(args)
    eles[0] = tpl
    args = tuple(eles)
    return template(*args, **kwargs)

def i18n_view(tmpl, **defaults):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            file = os.path.join("{lang!s}/".format(lang=request.app.lang), tmpl)
            result = func(*args, **kwargs)
            if isinstance(result, (dict, DictMixin)):
                tplvars = defaults.copy()
                tplvars.update(result)
                return template(file, **tplvars)
            elif result is None:
                return template(file, defaults)
            return result
        return wrapper
    return decorator


class I18NMiddleware(object):

    @property
    def header(self):
        return self._header

    @property
    def http_accept_language(self):
        return self.header.get('HTTP_ACCEPT_LANGUAGE')

    @property
    def app(self):
        return self._app

    def __init__(self, app, i18n, sub_app=True, *kw, **kwargs):
        """
        key `external_translators` in kwargs

        formalchemy allows application translator to pass in to translate
        application specified label per request environ, for example,
        `self.your_field.label(_(YOUR_LABEL))`, the translation of YOUR_LABEL
        is not resided in formalchemy, but your own application, so in this
        case we would like translator from the root application to translate
        it.

        formalchemy external translator environ key `fa.translate`

        i18n.I18NMiddleware(app, i18n_plugin,
            **{"external_translators": ["fa.translate"]})

        `explicit_redirect`
        assume default language is "de", url "/" is requested, if
        `explicit_redirect` is enabled, the lang code will be always prepended
        to the request url, so "/" becomes "/de".
        """
        self._app = app
        self.app.install(i18n)
        self._http_language = ""
        i18n.middleware = self

        self.translators = kwargs.get("external_translators")

        self.is_explicit_redirect = kwargs.get("explicit_redirect")

        if sub_app:
            for route in self.app.routes:
                if route.config.get('mountpoint'):
                    route.config.get('mountpoint').get('target').install(i18n)

    def __call__(self, environ, start_response):
        self._http_language = environ.get('HTTP_ACCEPT_LANGUAGE')
        self._header = environ
        locale = environ['PATH_INFO'].split('/')[1]
        for i18n in [plugin for plugin in self.app.plugins if plugin.name == 'i18n']:
            if locale in i18n.locales:
                self.app.lang = locale
                environ['PATH_INFO'] = environ['PATH_INFO'][len(locale)+1:]
            else:
                self.app.lang = i18n._default
                if self.is_explicit_redirect:
                    _url = "/{0}{1}".format(
                        i18n._default, environ['PATH_INFO'])
                    start_response('302 Found', [('Location', _url)],
                        sys.exc_info())
                    return []

        if self.translators:
            for translator in self.translators:
                environ[translator] = self.app._

        return self.app(environ, start_response)


Middleware = I18NMiddleware


class I18NPlugin(object):
    name = 'i18n'
    api = 2

    @property
    def middleware(self):
        return self._middleware

    @middleware.setter
    def middleware(self, middleware):
        self._middleware = middleware

    @property
    def keyword(self):
        return self._keyword

    @property
    def locales(self):
        return self._locales

    @property
    def local_dir(self):
        return self._locale_dir

    def __init__(self, domain, locale_dir, lang_code=None, default='en', keyword='i18n'):
        self.domain = domain
        if locale_dir is None:
            raise PluginError('No locale directory found, please assign a right one.')
        self._locale_dir = locale_dir

        self._locales = self._get_languages(self._locale_dir)
        self._default = default
        self._lang_code = lang_code

        self._cache = {}
        self._apps = []
        self._keyword = keyword

    def _get_languages(self, directory):
        return [dir for dir in os.listdir(self._locale_dir) if os.path.isdir(os.path.join(directory, dir))]

    def setup(self, app):
        self._apps.append(app)
        for app in self._apps:
            app._ = lambda s: s

            if hasattr(app, 'add_hook'):
                # attribute hooks was renamed to _hooks in version 0.12.x and add_hook method was introduced instead.
                app.add_hook('before_request', self.prepare)
            else:
                app.hooks.add('before_request', self.prepare)

            app.__class__.lang = property(fget=lambda x: self.get_lang(), fset=lambda x, value: self.set_lang(value))

    def parse_accept_language(self, accept_language):
        if accept_language == None:
            return []
        languages = accept_language.split(",")
        locale_q_pairs = []

        for language in languages:
            if language.split(";")[0] == language:
                # no q => q = 1
                locale_q_pairs.append((language.strip(), "1"))
            else:
                locale = language.split(";")[0].strip()
                q = language.split(";")[1].split("=")[1]
                locale_q_pairs.append((locale, q))

        return locale_q_pairs

    def detect_locale(self):
        locale_q_pairs = self.parse_accept_language(self.middleware.http_accept_language)
        for pair in locale_q_pairs:
            for locale in self._locales:
                if pair[0].replace('-', '_').lower().startswith(locale.lower()):
                    return locale

        return self._default

    def get_lang(self):
        return self._lang_code

    def set_lang(self, lang_code=None):
        self._lang_code = lang_code
        if self._lang_code is None:
            self._lang_code = self.detect_locale()

        self.prepare()

    def bytestring_decoded_gettext(self, value):
        if sys.version_info.major >= 3:
            return self.trans.gettext(value)
        else:
            _value = self.trans.gettext(value)
            return _value.decode(self.trans.charset())

    def prepare(self, *args, **kwargs):
        if self._lang_code is None:
            self._lang_code = self.detect_locale()

        if self._lang_code in self._cache.keys():
            self.trans = self._cache[self._lang_code]
            if self.trans:
                self.trans.install()
                for app in self._apps:
                    app._ = self.bytestring_decoded_gettext
            else:
                for app in self._apps:
                    app._ = lambda s: s
            return
        try:
            self.trans = gettext.translation(self.domain, self._locale_dir, languages=[self._lang_code])
            self.trans.install()
            for app in self._apps:
                app._ = self.bytestring_decoded_gettext
            self._cache[self._lang_code] = self.trans
        except Exception, e:
            for app in self._apps:
                app._ = lambda s: s
            self._cache[self._lang_code] = None

    def apply(self, callback, route):
        return callback


Plugin = I18NPlugin

### EOF ###
## vim:smarttab:sts=4:sw=4:et:ai:tw=80:


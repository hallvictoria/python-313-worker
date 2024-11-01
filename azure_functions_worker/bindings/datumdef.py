# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json
import logging

from datetime import datetime
from typing import Any, List, Optional

from .nullable_converters import (
    to_nullable_bool,
    to_nullable_double,
    to_nullable_string,
    to_nullable_timestamp,
)

from ..logging import logger

try:
    from http.cookies import SimpleCookie
except ImportError:
    from Cookie import SimpleCookie


class Datum:
    def __init__(self, value, type):
        self.value = value
        self.type = type

    @property
    def python_value(self) -> Any:
        if self.value is None or self.type is None:
            return None
        elif self.type in ('bytes', 'string', 'int', 'double'):
            return self.value
        elif self.type == 'json':
            return json.loads(self.value)
        elif self.type == 'collection_string':
            return [v for v in self.value.string]
        elif self.type == 'collection_bytes':
            return [v for v in self.value.bytes]
        elif self.type == 'collection_double':
            return [v for v in self.value.double]
        elif self.type == 'collection_sint64':
            return [v for v in self.value.sint64]
        else:
            return self.value

    @property
    def python_type(self) -> type:
        return type(self.python_value)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False

        return self.value == other.value and self.type == other.type

    def __hash__(self):
        return hash((type(self), (self.value, self.type)))

    def __repr__(self):
        val_repr = repr(self.value)
        if len(val_repr) > 10:
            val_repr = val_repr[:10] + '...'
        return '<Datum {} {}>'.format(self.type, val_repr)

    @classmethod
    def from_typed_data(cls, protos):
        try:
            td = protos.TypedData
        except Exception as ex:
            # Todo: better catch for Datum.from_typed_data(http.body) -- if the data being sent in is already protos.TypedData
            td = protos
        tt = td.WhichOneof('data')
        if tt == 'http':
            http = td.http
            val = dict(
                method=Datum(http.method, 'string'),
                url=Datum(http.url, 'string'),
                headers={
                    k: Datum(v, 'string') for k, v in http.headers.items()
                },
                body=(
                    Datum.from_typed_data(http.body)
                    or Datum(type='bytes', value=b'')
                ),
                params={
                    k: Datum(v, 'string') for k, v in http.params.items()
                },
                query={
                    k: Datum(v, 'string') for k, v in http.query.items()
                },
            )
        elif tt == 'string':
            val = td.string
        elif tt == 'bytes':
            val = td.bytes
        elif tt == 'json':
            val = td.json
        elif tt == 'collection_bytes':
            val = td.collection_bytes
        elif tt == 'collection_string':
            val = td.collection_string
        elif tt == 'collection_sint64':
            val = td.collection_sint64
        elif tt == 'model_binding_data':
            val = td.model_binding_data
        elif tt is None:
            return None
        else:
            raise NotImplementedError(
                'unsupported TypeData kind: {!r}'.format(tt)
            )

        return cls(val, tt)


def datum_as_proto(datum: Datum,  protos):
    if datum.type == 'string':
        return protos.TypedData(string=datum.value)
    elif datum.type == 'bytes':
        return protos.TypedData(bytes=datum.value)
    elif datum.type == 'json':
        return protos.TypedData(json=datum.value)
    elif datum.type == 'http':
        return protos.TypedData(http=protos.RpcHttp(
            status_code=datum.value['status_code'].value,
            headers={
                k: v.value
                for k, v in datum.value['headers'].items()
            },
            cookies=parse_to_rpc_http_cookie_list(datum.value.get('cookies'), protos),
            enable_content_negotiation=False,
            body=datum_as_proto(datum.value['body'], protos),
        ))
    elif datum.type is None:
        return None
    elif datum.type == 'dict':
        # TypedData doesn't support dict, so we return it as json
        return protos.TypedData(json=json.dumps(datum.value))
    elif datum.type == 'list':
        # TypedData doesn't support list, so we return it as json
        return protos.TypedData(json=json.dumps(datum.value))
    elif datum.type == 'int':
        return protos.TypedData(int=datum.value)
    elif datum.type == 'double':
        return protos.TypedData(double=datum.value)
    elif datum.type == 'bool':
        # TypedData doesn't support bool, so we return it as an int
        return protos.TypedData(int=int(datum.value))
    else:
        raise NotImplementedError(
            'unexpected Datum type: {!r}'.format(datum.type)
        )


def parse_to_rpc_http_cookie_list(cookies: Optional[List[SimpleCookie]], protos):
    if cookies is None:
        return cookies

    rpc_http_cookies = []

    for cookie in cookies:
        for name, cookie_entity in cookie.items():
            rpc_http_cookies.append(
                protos.RpcHttpCookie(name=name,
                                     value=cookie_entity.value,
                                     domain=to_nullable_string(
                                         cookie_entity['domain'],
                                         'cookie.domain',
                                         protos),
                                     path=to_nullable_string(
                                         cookie_entity['path'],
                                         'cookie.path',
                                         protos),
                                     expires=to_nullable_timestamp(
                                         parse_cookie_attr_expires(
                                             cookie_entity), 'cookie.expires',
                                         protos),
                                     secure=to_nullable_bool(
                                         bool(cookie_entity['secure']),
                                         'cookie.secure',
                                         protos),
                                     http_only=to_nullable_bool(
                                         bool(cookie_entity['httponly']),
                                         'cookie.httpOnly',
                                         protos),
                                     same_site=parse_cookie_attr_same_site(
                                         cookie_entity, protos),
                                     max_age=to_nullable_double(
                                         cookie_entity['max-age'],
                                         'cookie.maxAge',
                                         protos)))

    return rpc_http_cookies


def parse_cookie_attr_expires(cookie_entity):
    expires = cookie_entity['expires']

    if expires is not None and len(expires) != 0:
        try:
            return datetime.strptime(expires, "%a, %d %b %Y %H:%M:%S GMT")
        except ValueError:
            logging.error(
                f"Can not parse value {expires} of expires in the cookie "
                f"due to invalid format.")
            raise
        except OverflowError:
            logging.error(
                f"Can not parse value {expires} of expires in the cookie "
                f"because the parsed date exceeds the largest valid C "
                f"integer on your system.")
            raise

    return None


def parse_cookie_attr_same_site(cookie_entity, protos):
    same_site = getattr(protos.RpcHttpCookie.SameSite, "None")
    try:
        raw_same_site_str = cookie_entity['samesite'].lower()

        if raw_same_site_str == 'lax':
            same_site = protos.RpcHttpCookie.SameSite.Lax
        elif raw_same_site_str == 'strict':
            same_site = protos.RpcHttpCookie.SameSite.Strict
        elif raw_same_site_str == 'none':
            same_site = protos.RpcHttpCookie.SameSite.ExplicitNone
    except Exception:
        return same_site

    return same_site

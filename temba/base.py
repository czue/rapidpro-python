from __future__ import absolute_import, unicode_literals

import datetime
import json
import requests

from abc import ABCMeta
from .types import TembaException, TembaType, format_iso8601


class AbstractTembaClient(object):
    """
    Abstract and version agnostic base client class
    """
    __metaclass__ = ABCMeta

    def __init__(self, host, token, ssl=True, debug=False):
        if host.startswith('http'):
            self.root_url = host
        else:
            self.root_url = '%s://%s/api/v1' % ('https' if ssl else 'http', host)

        self.token = token
        self.debug = debug

    def _get_single(self, endpoint, params):
        """
        GETs a single result from the given endpoint. Throws an exception if there are no or multiple results.
        """
        url = '%s/%s.json' % (self.root_url, endpoint)
        response = self._request('get', url, params=params)

        num_results = len(response['results'])

        if num_results > 1:
            raise TembaException("Request for single object returned %d objects" % num_results)
        elif num_results == 0:
            raise TembaException("Request for single object returned no objects")
        else:
            return response['results'][0]

    def _get_all(self, endpoint, params):
        """
        GETs all results from the given endpoint
        """
        num_requests = 0
        results = []

        url = '%s/%s.json' % (self.root_url, endpoint)
        while url:
            response = self._request('get', url, params=params)
            num_requests += 1
            results += response['results']
            url = response['next']

        return results

    def _post_single(self, endpoint, payload):
        """
        POSTs to the given endpoint which must return a single item
        """
        url = '%s/%s.json' % (self.root_url, endpoint)
        return self._request('post', url, body=payload)

    def _delete(self, endpoint, params):
        """
        DELETEs to the given endpoint which won't return anything
        """
        url = '%s/%s.json' % (self.root_url, endpoint)
        self._request('delete', url, params=params)

    def _request(self, method, url, body=None, params=None):
        """
        Makes a GET or POST request to the given URL and returns the parsed JSON
        """
        headers = {'Content-type': 'application/json',
                   'Accept': 'application/json',
                   'Authorization': 'Token %s' % self.token}

        if self.debug:
            print "%s %s %s" % (method.upper(), url, json.dumps(params if params else body))

        try:
            args = {'headers': headers}
            if body:
                args['data'] = json.dumps(body)
            if params:
                args['params'] = params

            response = requests.request(method, url, **args)

            if self.debug:
                print " -> %s" % response.content

            response.raise_for_status()

            return response.json() if response.content else None
        except requests.HTTPError, ex:
            raise TembaException("Request error", ex)

    def _build_params(self, **kwargs):
        return self._build_data(kwargs, True)

    def _build_body(self, **kwargs):
        return self._build_data(kwargs, False)

    @classmethod
    def _build_data(cls, data, flat):
        """
        Helper method to build data for a POST body or query string. Converts Temba objects to ids and UUIDs and removes
        None values.
        """
        params = {}
        for kwarg, value in data.iteritems():
            if value is None:
                continue
            else:
                params[kwarg] = cls._serialize_value(value, flat)
        return params

    @classmethod
    def _serialize_value(cls, value, flat):
        if isinstance(value, list) or isinstance(value, tuple):
            serialized = []
            for item in value:
                serialized.append(cls._serialize_value(item, flat))
            return ','.join(serialized) if flat else serialized
        elif isinstance(value, TembaType):
            if hasattr(value, 'uuid'):
                return value.uuid
            elif hasattr(value, 'id'):
                return value.id
        elif isinstance(value, datetime.datetime):
            return format_iso8601(value)
        else:
            return value

#!/usr/bin/env python
# encoding: utf-8
from unittest import mock

import json
from falcon.testing import TestCase

from settings import SettingsResource
from util import redis_client


redis = redis_client()


class TestSettingsResource(TestCase):
    def setUp(self):
        super().setUp()
        self.api.add_route('/settings', SettingsResource())
        redis.flushdb()

    def test_sending_bad_json(self):
        resp = self.simulate_put('/settings', body='boo')
        assert resp.status_code == 400

    def test_adds_a_new_setting(self):
        data = {'outages': ['recommendations']}
        resp = self.simulate_put('/settings', body=json.dumps(data))
        assert resp.json == data
        assert redis.smembers('outages') == {'recommendations'}

    def test_replaces_existing_settings(self):
        # Set initial settings
        self.simulate_put('/settings', body=json.dumps({
            'outages': ['homepage']
        }))
        # Overwrite initial settings
        resp = self.simulate_put('/settings', body=json.dumps({
            'outages': ['recommendations']
        }))

        expected = {'outages': ['recommendations']}
        assert resp.json == expected
        assert redis.smembers('outages') == {'recommendations'}

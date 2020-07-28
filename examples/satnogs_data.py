import requests


class SatNOGSNetwork(object):
    def __init__(self, config):
        self.url = config['default']['NETWORK_API_URL']
        self.key = config['default']['NETWORK_API_KEY']
        self.params = config['default']['NETWORK_PARAMS']
        self.header = self._get_header()

    def _get_header(self):
        token = self.key
        return {'Authorization': 'Token ' + token}

    def get_observations(self):
        return requests.get(self.url, headers=self.header, params=self.params)

    def get_observation(self, observation_id):
        return requests.get(self.url, headers=self.header, params={"id": observation_id})

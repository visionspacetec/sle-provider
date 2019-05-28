from zope.interface import implementer
from twisted.cred.portal import IRealm
from twisted.web import resource
from ..restfulManager import RestfulManager


@implementer(IRealm)
class Realm:

    def initialize(self, container, sle_config, commands):
        self.container = container
        self.sle_config = sle_config
        self.commands = commands

    def requestAvatar(self, avatarId, mind, *interfaces):
        if resource.IResource in interfaces:
            root = RestfulManager()
            root.container = self.container
            root.sle_config = self.sle_config
            root.commands = self.commands
            return resource.IResource, root.app.resource(), lambda: None
        raise NotImplementedError()

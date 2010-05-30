# vim: tabstop=4 shiftwidth=4 softtabstop=4
# Copyright [2010] [Anso Labs, LLC]
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""
Datastore Model objects for Compute Instances, with
InstanceDirectory manager.

# Create a new instance?
>>> InstDir = InstanceDirectory()
>>> inst = InstDir.new()
>>> inst.destroy()
True
>>> inst = InstDir['i-123']
>>> inst['ip'] = "192.168.0.3"
>>> inst['project_id'] = "projectA"
>>> inst.save()
True

>>> InstDir['i-123']
<Instance:i-123>
>>> InstDir.all.next()
<Instance:i-123>

>>> inst.destroy()
True
"""

from nova import vendor

from nova import datastore
from nova import flags
from nova import utils


FLAGS = flags.FLAGS

flags.DEFINE_string('instances_prefix', 'compute-',
                    'prefix for keepers for instances')

# TODO(ja): singleton instance of the directory
class InstanceDirectory(object):
    """an api for interacting with the global state of instances """
    def __init__(self):
        self.keeper = datastore.Keeper(FLAGS.instances_prefix)

    def get(self, instance_id):
        """ returns an instance object for a given id """
        return Instance(instance_id)

    def __getitem__(self, item):
        return self.get(item)

    def by_project(self, project):
        """ returns a list of instance objects for a project """
        for instance_id in self.keeper.smembers('project:%s:instances' % project):
            yield Instance(instance_id)

    def by_node(self, node_id):
        """ returns a list of instances for a node """

        for instance in self.all:
            if instance['node_name'] == node_id:
                yield instance

    def by_ip(self, ip_address):
        """ returns an instance object that is using the IP """
        for instance in self.all:
            if instance['private_dns_name'] == ip_address:
                return instance
        return None

    def by_volume(self, volume_id):
        """ returns the instance a volume is attached to """
        pass

    def exists(self, instance_id):
        return self.keeper.set_is_member('instances', instance_id)

    @property
    def all(self):
        """ returns a list of all instances """
        for instance_id in self.keeper.set_members('instances'):
            yield Instance(instance_id)

    def new(self):
        """ returns an empty Instance object, with ID """
        instance_id = utils.generate_uid('i')
        return self.get(instance_id)



class Instance(object):
    """ Wrapper around stored properties of an instance """

    def __init__(self, instance_id):
        """ loads an instance from the datastore if exists """
        self.keeper = datastore.Keeper(FLAGS.instances_prefix)
        self.instance_id = instance_id
        self.initial_state = {}
        self.state = self.keeper[self.__redis_key]
        if self.state:
            self.initial_state = self.state
        else:
            self.state = {'state': 'pending',
                          'instance_id': instance_id,
                          'node_name': 'unassigned',
                          'project_id': 'unassigned',
                          'user_id': 'unassigned'
                         }

    @property
    def __redis_key(self):
        """ Magic string for instance keys """
        return 'instance:%s' % self.instance_id

    def __repr__(self):
        return "<Instance:%s>" % self.instance_id

    def get(self, item, default):
        return self.state.get(item, default)

    def __getitem__(self, item):
        return self.state[item]

    def __setitem__(self, item, val):
        self.state[item] = val
        return self.state[item]

    def __delitem__(self, item):
        """ We don't support this """
        raise Exception("Silly monkey, Instances NEED all their properties.")

    def save(self):
        """ update the directory with the state from this instance
        make sure you've set the project_id and user_id before you call save
        for the first time.
        """
        # TODO(ja): implement hmset in redis-py and use it
        # instead of multiple calls to hset
        state = self.keeper[self.__redis_key]
        if not state:
            state = {}
        for key, val in self.state.iteritems():
            # if (not self.initial_state.has_key(key)
            # or self.initial_state[key] != val):
                state[key] = val
        self.keeper[self.__redis_key] = state
        if self.initial_state == {}:
            self.keeper.set_add('project:%s:instances' % self.project,
                                self.instance_id)
            self.keeper.set_add('instances', self.instance_id)
        self.initial_state = self.state
        return True

    @property
    def project(self):
        if self.state.get('project_id', None):
            return self.state['project_id']
        return self.state.get('owner_id', 'unassigned')

    def destroy(self):
        """ deletes all related records from datastore.
        does NOT do anything to running libvirt state.
        """
        self.keeper.set_remove('project:%s:instances' % self.project,
                               self.instance_id)
        del self.keeper[self.__redis_key]
        self.keeper.set_remove('instances', self.instance_id)
        return True

    @property
    def volumes(self):
        """ returns a list of attached volumes """
        pass

    @property
    def reservation(self):
        """ Returns a reservation object """
        pass

# class Reservation(object):
# """ ORM wrapper for a batch of launched instances """
# def __init__(self):
# pass
#
# def userdata(self):
# """ """
# pass
#
#
# class NodeDirectory(object):
# def __init__(self):
# pass
#

if __name__ == "__main__":
    import doctest
    doctest.testmod()

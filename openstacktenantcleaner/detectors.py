from datetime import timedelta

from typing import Callable, Tuple, Pattern, Iterable, Set

from openstacktenantcleaner.common import create_human_identifier
from openstacktenantcleaner.managers import OpenstackInstanceManager
from openstacktenantcleaner.models import OpenstackItem, OpenstackCredentials, OpenstackImage, OpenstackKeypair, \
    OpenstackInstance
from openstacktenantcleaner.tracking import Tracker

ShouldPreventDeleteAndReason = Tuple[bool, str]
PreventDeleteDetector = Callable[[OpenstackItem, OpenstackCredentials, Tracker, Set[OpenstackItem]],
                                 ShouldPreventDeleteAndReason]


def prevent_delete_protected_image_detector(image: OpenstackImage, openstack_credentials: OpenstackCredentials,
                                            tracker: Tracker,  already_marked_for_deletion: Set[OpenstackItem])\
        -> ShouldPreventDeleteAndReason:
    """
    Detects when an image delete should be prevented because the OpenStack image is marked as protected.
    :param image: the image of interest
    :param openstack_credentials: credentials to access OpenStack
    :param tracker: OpenStack item history tracker
    :param already_marked_for_deletion: OpenStack items already marked for deletion in other reports
    :return: whether to prevent deletion of the item and the reason for the decision
    """
    return image.protected, f"Image is {'' if image.protected else 'not '}marked on OpenStack as protected"


def prevent_delete_image_in_use_detector(image: OpenstackImage, openstack_credentials: OpenstackCredentials,
                                         tracker: Tracker, already_marked_for_deletion: Set[OpenstackItem]) \
        -> ShouldPreventDeleteAndReason:
    """
    Detects when an image delete should be prevented because the image is in use by an OpenStack instance. 
    :param image: the image of interest
    :param openstack_credentials: credentials to access OpenStack
    :param tracker: OpenStack item history tracker
    :param already_marked_for_deletion: OpenStack items already marked for deletion in other reports
    :return: whether to prevent deletion of the item and the reason for the decision
    """
    instance_manager = OpenstackInstanceManager(openstack_credentials)
    instances = instance_manager.get_all()
    instances_marked_for_deletion = {item for item in already_marked_for_deletion if type(item) == OpenstackInstance}
    for instance in instances:
        if instance.image == image.identifier and instance not in instances_marked_for_deletion:
            return True, f"Image cannot be deleted because it is in use by the instance " \
                         f"{create_human_identifier(instance)}"
    return False, f"No instances are using the image"


def prevent_delete_key_pair_in_use_detector(key_pair: OpenstackKeypair, openstack_credentials: OpenstackCredentials,
                                            tracker: Tracker, already_marked_for_deletion: Set[OpenstackItem])\
        -> ShouldPreventDeleteAndReason:
    """
    Detects when an key-pair delete should be prevented because it is in use by an OpenStack instance.
    :param key_pair:  the key-pair of interest
    :param openstack_credentials: credentials to access OpenStack
    :param tracker: OpenStack item history tracker
    :param already_marked_for_deletion: OpenStack items already marked for deletion in other reports
    :return: whether to prevent deletion of the item and the reason for the decision
    """
    instance_manager = OpenstackInstanceManager(openstack_credentials)
    instances_marked_for_deletion = {item for item in already_marked_for_deletion if type(item) == OpenstackInstance}
    for instance in instance_manager.get_all():
        if instance.key_name == key_pair.name and instance not in instances_marked_for_deletion:
            return True, f"Key pair in use by instance {create_human_identifier(instance)}"
    return False, "No instances are using the key pair"


def create_delete_if_older_than_detector(age: timedelta) -> PreventDeleteDetector:
    """
    Creates a detector that prevents an item from being deleted if younger (or equal) to the given age.
    :param age: the age after which items can be deleted
    :return: the created detector
    """
    def detector(item: OpenstackItem, credentials: OpenstackCredentials, tracker: Tracker,
                 already_marked_for_deletion: Set[OpenstackItem]):
        item_age = tracker.get_age(item)
        prevent_delete = item_age <= age
        return prevent_delete, f"Item age: {item_age} - {'not ' if prevent_delete else ''}older than: {age}"

    return detector


def create_exclude_detector(excludes: Iterable[Pattern]) -> PreventDeleteDetector:
    """
    Creates a detector that prevents an image from being deleted if its name matches on one of the given regexes.
    :param excludes: the exclude regexes
    :return: the created detector
    """
    def detector(item: OpenstackItem, credentials: OpenstackCredentials, tracker: Tracker,
                 already_marked_for_deletion: Set[OpenstackItem]):
        for exclude in excludes:
            if exclude.fullmatch(item.name) is not None:
                return True, f"Exclude matched: {exclude.pattern}"
        return False, f"Excludes not matched: {[exclude.pattern for exclude in excludes]}"

    return detector

import os
import xml
import six
import warnings
import traceback
import logging
from datetime import datetime
from datetime import date
from datetime import time

from metadata_constructors import MetadataItem
from metadata_constructors import MetadataValueList
from metadata_constructors import MetadataParentItem
from metadata_constructors import MetadataObjectList
from metadata_constructors import MetadataValueListHelper
from metadata_constructors import MetadataObjectListHelper

from metadata_items import MetadataLanguage

from elements import elements
from languages import languages

# TODO: Have logger handle deprecation warnings
# turn on warnings for deprecation once
warnings.simplefilter('once', DeprecationWarning)
# Make warnings look nice
def warning_on_one_line(message, category, filename, lineno, file=None, line=None):
    return '{0}: {1}\n'.format(category.__name__, message)
warnings.formatwarning = warning_on_one_line



class XMLEditor(object):
    """
    The metadata editor
    Create an instance of this object for each metadata file you want to edit
    """

    def __init__(self, metadata_file=None, formid=None, version=None,
                 items=None, loglevel='INFO'):

        screen_handler = None
        self.logger = logging.getLogger("__name__")
        if not len(self.logger.handlers):
            screen_handler = logging.StreamHandler()  # set up the logging level at debug, but only write INFO or higher to the screen
            self.logger.setLevel(logging.DEBUG)
            self.logger.addHandler(screen_handler)
        else:
            for handler in self.logger.handlers:
                # take the first one available
                if isinstance(handler, logging.StreamHandler):
                    screen_handler = handler
                    break

            # just making sure that there is a screenhandler
            if screen_handler is None:
                screen_handler = logging.StreamHandler()
                self.logger.setLevel(logging.DEBUG)
                self.logger.addHandler(screen_handler)

        if loglevel.upper() == "CRITICAL":
            screen_handler.setLevel(logging.CRITICAL)
        elif loglevel.upper() == "ERROR":
            screen_handler.setLevel(logging.ERROR)
        elif loglevel.upper() == "WARNING":
            screen_handler.setLevel(logging.WARNING)
        elif loglevel.upper() == "INFO":
            screen_handler.setLevel(logging.INFO)
        elif loglevel.upper() == "DEBUG":
            screen_handler.setLevel(logging.DEBUG)
        else:
            screen_handler.setLevel(logging.NOTSET)


        self.logger.debug("Set logging mode to {0}".format(loglevel))

        if items is None:
            items = list()

        self.items = items
        self.metadata_file = metadata_file
        self.elements = xml.etree.ElementTree.ElementTree()
        self.formid = formid
        self.version = version
        if self.version is None:
            # TODO: create version number
            pass

        self.data_type = 'MetadataFile'
        if self.metadata_file.endswith('.xml'):
            if not os.path.exists(self.metadata_file):
                self._create_xml_file(self.metadata_file)
            self._workspace_type = 'FileSystem'
        else:
            raise TypeError("Metadata file is not an XML file. Check file extension")

        self.elements.parse(self.metadata_file)

        # create these all after the parsing happens so that if they have any self initialization, they can correctly perform it

        for name in elements.keys():
            if "sync" in elements[name].keys():
                sync = elements[name]["sync"]
            else:
                sync = None

            if "unsupported" in elements[name].keys():
                if self.data_type in elements[name]["unsupported"]:
                    self.logger.debug("{0} not supported for {1}. SKIP".format(name, self.data_type))
                    continue

            setattr(self, "_{0!s}".format(name), None)

            if elements[name]['type'] in ["string", "datetime", "date", "time", "integer", "float"]:
                setattr(self, "_{0}".format(name), MetadataItem(elements[name]['path'], name, self, sync))
                if self.__dict__["_{0}".format(name)].value is not None:
                    setattr(self, name, self.__dict__["_{0}".format(name)].value.strip())
                else:
                    setattr(self, name, self.__dict__["_{0}".format(name)].value)

            elif elements[name]['type'] == "attribute":
                setattr(self, "_{0}".format(name), MetadataItem(elements[name]['path'], name, self, sync))
                if isinstance(self.__dict__["_{0}".format(name)].attributes, dict):
                    key = elements[name]['key']
                    values = elements[name]['values']
                    if key in self.__dict__["_{0}".format(name)].attributes.keys():
                        v = self.__dict__["_{0}".format(name)].attributes[elements[name]['key']]
                        for value in values:
                            if v in value:
                                setattr(self, name, value[0])
                                break
                else:
                    setattr(self, name, None)

            elif elements[name]['type'] == "list":
                setattr(self, "_{0}".format(name), MetadataValueList(elements[name]["tagname"], elements[name]['path'], name, self, sync))
                #setattr(self, name, self.__dict__["_{}".format(name)].value)
                #setattr(self, name, ListValues(self.__dict__["_{}".format(name)], name))

            elif elements[name]['type'] == "language":
                setattr(self, "_{0}".format(name), MetadataLanguage(elements[name]['path'], name, self, sync))
                if self.__dict__["_{0}".format(name)].value is not None:
                    setattr(self, name, self.__dict__["_{0}".format(name)].value.strip())
                else:
                    setattr(self, name, self.__dict__["_{0}".format(name)].value)

            # TODO: turn on sync
            elif elements[name]['type'] == "parent_item":
                setattr(self, "_{0}".format(name), MetadataParentItem(elements[name]['path'], self, elements[name]['elements']))
                setattr(self, name, self.__dict__["_{0}".format(name)])

            elif elements[name]['type'] == "object_list":
                setattr(self, "_{0}".format(name), MetadataObjectList(elements[name]["tagname"], elements[name]['path'], self, elements[name]['elements'], sync))
                #setattr(self, name, self.__dict__["_{}".format(name)])

            if elements[name] in self.__dict__.keys():
                self.items.append(getattr(self, "_{0}".format(elements[name])))

        if items:
            self.initialize_items()

    def _create_xml_file(self, xml_file):
        with open(xml_file, "w") as f:
            self.logger.debug("Create new file {0!s}".format(xml_file))
            f.write('<?xml version="1.0" ?><{0} xmlns:jr="http://openrosa.org/javarosa" xmlns:orx="http://openrosa.org/xforms" id="{0}" version="{1}"></{0}>'.format(self.formid, self.version))

    def __setattr__(self, n, v):
        """
        Check if input value type matches required type for metadata element
        and write value to internal property
        :param n: string
        :param v: string
        :return:
        """

        if n in elements.keys():

            # Warn if property got deprecated, but only if call is made by user, not during initialization
            if "deprecated" in elements[n].keys() and traceback.extract_stack()[-2][2] != "__init__":
                warnings.warn("Call to deprecated property {0}. {1}".format(n, elements[n]["deprecated"]), category=DeprecationWarning)

            if elements[n]['type'] == "string":
                if isinstance(v, (str, six.text_type)):
                    self.__dict__["_{0}".format(n)].value = v
                elif v is None:
                    self.__dict__["_{0}".format(n)].value = ""
                else:
                    raise RuntimeWarning("Input value must be of type String")

            elif elements[n]['type'] == "datetime":

                if isinstance(v, datetime):
                    self.__dict__["_{0}".format(n)].value = datetime.strftime(v, "%Y-%m-%dT%H:%M:%S")
                elif isinstance(v, (str, six.text_type)):

                    # remove all whitespaces for easier handling
                    v = "".join(v.split())

                    try:
                        if len(v) == 8:
                            # try first to convert to datetime to check if format is correct
                            # then write string to file
                            new_value = datetime.strptime(v, "%Y%m%d")
                            self.__dict__["_{0}".format(n)].value = new_value.isoformat()
                        elif len(v) == 10:
                            # try first to convert to datetime to check if format is correct
                            # then write string to file
                            new_value = datetime.strptime(v, "%Y-%m-%d")
                            self.__dict__["_{0}".format(n)].value = new_value.isoformat()

                        else:
                            # try first to convert to datetime to check if format is correct
                            # then write string to fil
                            new_value = datetime.strptime(v, "%Y-%m-%dT%H:%M:%S")
                            self.__dict__["_{0}".format(n)].value = new_value.isoformat()

                    except ValueError:
                        RuntimeWarning(
                            "Input value must be of type a Datetime or a String ('%Y%m%d', '%Y-%m-%d' or '%Y-%m-%dT%H:%M:%S')")
                elif v is None:
                    self.__dict__["_{0}".format(n)].value = ""
                else:
                    raise RuntimeWarning("Input value must be of type a Date or a String ('yyyymmdd')")

            elif elements[n]['type'] == "date":
                if isinstance(v, date):
                    self.__dict__["_{0}".format(n)].value = datetime.strftime(v, "%Y-%m-%d")
                elif isinstance(v, (str, six.text_type)):

                    # remove all whitespaces for easier handling
                    v = "".join(v.split())

                    try:
                        if len(v) == 8:
                            # try first to convert to datetime to check if format is correct
                            # then write string to file
                            new_value = datetime.strptime(v, "%Y%m%d")
                            self.__dict__["_{0}".format(n)].value = new_value.date().isoformat()
                        elif len(v) == 10:
                            # try first to convert to datetime to check if format is correct
                            # then write string to file
                            new_value = datetime.strptime(v, "%Y-%m-%d")
                            self.__dict__["_{0}".format(n)].value = new_value.date().isoformat()

                        else:
                            # try first to convert to datetime to check if format is correct
                            # then write string to fil
                            new_value = datetime.date().strptime(v, "%Y-%m-%d")
                            self.__dict__["_{0}".format(n)].value = new_value.date().isoformat()

                    except ValueError:
                        RuntimeWarning("Input value must be of type a Datetime.date or a String ('%Y%m%d' or '%Y-%m-%d'")
                elif v is None:
                    self.__dict__["_{0}".format(n)].value = ""
                else:
                    raise RuntimeWarning("Input value must be of type a Date or a String ('yyyymmdd')")

            elif elements[n]['type'] == "time":
                if isinstance(v, time):
                    self.__dict__["_{0}".format(n)].value = datetime.strftime(v, "%H:%M:%S")
                elif isinstance(v, (str, six.text_type)):

                    # remove all whitespaces for easier handling
                    v = "".join(v.split())

                    try:
                        if len(v) == 8 and v.find(":") == -1:
                            new_value = datetime.strptime(v, "%H%M%S%f")
                            self.__dict__["_{0}".format(n)].value = new_value.time().isoformat()
                        elif len(v) <= 8:
                            # try first to convert to datetime to check if format is correct
                            # then write string to file
                            new_value = datetime.strptime(v, "%H:%M:%S")
                            self.__dict__["_{0}".format(n)].value = new_value.time().isoformat()
                        else:
                            # try first to convert to datetime to check if format is correct
                            # then write string to file
                            new_value = datetime.strptime(v, "%I:%M:%S%p")
                            self.__dict__["_{0}".format(n)].value = new_value.time().isoformat()

                    except ValueError:
                        RuntimeWarning(
                            "Input value must be of type a Datetime.time or a String ('%H:%M:%S' or '%I:%M:%S%p')")
                elif v is None:
                    self.__dict__["_{0}".format(n)].value = ""
                else:
                    raise RuntimeWarning("Input value must be of type a tatetime.time or a String ('HH:MM:SS')")

            elif elements[n]['type'] == "integer":
                if isinstance(v, int):
                    self.__dict__["_{0}".format(n)].value = str(v)
                elif isinstance(v, str):
                    try:
                        new_value = int(v)
                        self.__dict__["_{0}".format(n)].value = str(new_value)
                    except ValueError:
                        RuntimeWarning("Input value must be of type Integer")
                elif v is None:
                    self.__dict__["_{0}".format(n)].value = ""
                else:
                    raise RuntimeWarning("Input value must be of type Integer")

            elif elements[n]['type'] == "float":
                if isinstance(v, float):
                    self.__dict__["_{0}".format(n)].value = str(v)
                elif isinstance(v, (str, six.text_type)):
                    try:
                        new_value = float(v)
                        self.__dict__["_{0}".format(n)].value = str(new_value)
                    except ValueError:
                        RuntimeWarning("Input value must be of type Float")
                elif v is None:
                    self.__dict__["_{0}".format(n)].value = ""
                else:
                    raise RuntimeWarning("Input value must be of type Float")

            elif elements[n]['type'] == 'attribute':
                key = elements[n]['key']
                values = elements[n]['values']
                if isinstance(v,(str, six.text_type)):
                    done = False
                    for value in values:
                        if v in value:
                            self.__dict__["_{0}".format(n)].attributes[key] = value[1]
                            done = True
                            break
                    if not done:
                        raise RuntimeWarning("Input value must be one of: {0}".format(values))
                else:
                    raise RuntimeWarning("Input value must be one of: {0}".format(values))

            elif elements[n]['type'] == "list":
                if isinstance(v, list):
                    #self.__dict__[n].value = ListValues(self.__dict__["_{}".format(n)], v)
                    self.__dict__["_{0}".format(n)].value = v
                elif isinstance(v, MetadataValueListHelper):
                    self.__dict__["_{0}".format(n)].value = v
                else:
                    raise RuntimeWarning("Input value must be of type List")

            elif elements[n]['type'] == "language":
                if v in languages.keys():
                    #self.__dict__["_{}".format(n)].value = v
                    self.__dict__["_{0}".format(n)].attr_lang = {"value": languages[v][0]}
                    self.__dict__["_{0}".format(n)].attr_country = {"value": languages[v][1]}
                    a = 1
                elif v is None:
                    self.__dict__["_{0}".format(n)].value = ""
                else:
                    raise RuntimeWarning("Input value must be in {0}, an empty String or None".format(str(languages.keys())))

            elif elements[n]['type'] == "parent_item":
                if isinstance(v, MetadataParentItem):
                    self.__dict__["_{0!s}".format(n)] = v
                else:
                    raise RuntimeWarning("Input value must be a MetadataParentItem object")

            elif elements[n]['type'] == "object_list":
                if isinstance(v, list):
                    self.__dict__["_{0}".format(n)].value = v
                elif isinstance(v, MetadataObjectList):
                    self.__dict__["_{0}".format(n)].value = v
                else:
                    raise RuntimeWarning("Input value must be a MetadataOnlineResource object")

        else:
            self.__dict__[n] = v

    def __getattr__(self, n):
        """
        Type cast output values according to required element type
        :param n: string
        :return:
        """
        if n in elements.keys():

            # Warn if property got deprecated
            if "deprecated" in elements[n].keys():
                warnings.warn("Call to deprecated property {0}. {1}".format(n, elements[n]["deprecated"]), category=DeprecationWarning)

            if self.__dict__["_{0}".format(n)].value == "" and elements[n]['type'] in ["integer", "float", "datetime", "date", "time"]:
                return None
            elif elements[n]['type'] == "integer":
                return int(self.__dict__["_{0}".format(n)].value)
            elif elements[n]['type'] == "float":
                return float(self.__dict__["_{0}".format(n)].value)

            elif elements[n]['type'] == "datetime":
                if len(self.__dict__["_{0}".format(n)].value) == 8:
                    return datetime.strptime(self.__dict__["_{0}".format(n)].value, "%Y%m%d")
                elif len(self.__dict__["_{0}".format(n)].value) == 10:
                    return datetime.strptime(self.__dict__["_{0}".format(n)].value, "%Y-%m-%d")
                else:
                    return datetime.strptime(self.__dict__["_{0}".format(n)].value, "%Y-%m-%dT%H:%M:%S")
            elif elements[n]['type'] == "date":
                if len(self.__dict__["_{0}".format(n)].value) == 8:
                    return datetime.strptime(self.__dict__["_{0}".format(n)].value, "%Y%m%d").date()
                else:
                    return datetime.strptime(self.__dict__["_{0}".format(n)].value, "%Y-%m-%d").date()
            elif elements[n]['type'] == "time":
                if len(self.__dict__["_{0}".format(n)].value) == 8 and self.__dict__["_{0}".format(n)].value.find(":") == -1:
                    return datetime.strptime(self.__dict__["_{0}".format(n)].value, "%H%M%S%f").time()
                elif len(self.__dict__["_{0}".format(n)].value) <= 8:
                    return datetime.strptime(self.__dict__["_{0}".format(n)].value, "%H:%M:%S").time()
                else:
                    return datetime.strptime(self.__dict__["_{0}".format(n)].value, "%I:%M:%S%p")

            elif elements[n]['type'] == "parent_item":
                return self.__dict__["_{0}".format(n)]
            elif elements[n]['type'] == "language":
                return self.__dict__["_{0}".format(n)].get_lang()
            elif elements[n]['type'] == 'attribute':
                key = elements[n]['key']
                values = elements[n]['values']
                if key in self.__dict__["_{0}".format(n)].attributes:
                    v = self.__dict__["_{0}".format(n)].attributes[key]
                    for value in values:
                        if v in value:
                            return value[0]
                else:
                    return None
            elif elements[n]['type'] == "list":
                return MetadataValueListHelper(self.__dict__["_{0}".format(n)])
            elif elements[n]['type'] == "object_list":
                return MetadataObjectListHelper(self.__dict__["_{0}".format(n)])
            else:
                return self.__dict__["_{0}".format(n)].value
        else:
            # return self.__dict__["_{}".format(n)]
            return self.__dict__[n]




    def initialize_items(self):
        """
        Initialize all items
        :return:
        """
        for item in self.items:
            item.parent = self

    def rm_gp_history(self):
        """
        Remove all items form the geoprocessing history
        :return:
        """
        element = self.elements.find("Esri/DataProperties/lineage")
        if element is not None:
            i = 0
            children = element.findall("Process")
            for child in children:
                element.remove(child)
                i += 1
            self.logger.info("Remove {0} item(s) from the geoprocessing history".format(i))
        else:
            self.logger.info("There are no items in the geoprocessing history")


    def save(self, Enable_automatic_updates=False):
        """
        Save pending edits to file
        If feature class, import temporary XML file back into GDB

        :param Enable_automatic_updates: boolean
        :return:
        """
        self.logger.info("Saving metadata")

        # Write meta-metadata

        #if not self.formhub_uuid:
        #    self.formhub_uuid =
        #if not self.instance_id:
        #    self.meta_create_time =
        #if not self.instance_version:
        #    self.instance_version =

        for item in self.items:  # TODO: What's going on here?
            try:
                self.logger.debug(item.value)
            except:
                self.logger.warn(item)

        self.elements.write(self.metadata_file)  # overwrites itself


    def cleanup(self):
        """
        Remove all temporary files
        :return:
        """
        try:
            self.logger.debug("cleaning up from metadata operation")
            if self._workspace_type != 'FileSystem':
                if os.path.exists(self.metadata_file):
                    os.remove(self.metadata_file)

                xsl_extras = self.metadata_file + "_xslttransfor.log"
                if os.path.exists(xsl_extras):
                    os.remove(xsl_extras)

        except:
            self.logger.warn("Unable to remove temporary metadata files")

    def finish(self, Enable_automatic_updates=False):
        """
        Alias for saving and cleaning up
        :param Enable_automatic_updates: boolean
        :return:
        """
        self.save(Enable_automatic_updates)
        self.cleanup()

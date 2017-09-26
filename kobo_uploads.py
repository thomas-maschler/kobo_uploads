
import requests
from requests.auth import HTTPBasicAuth
import json
from xml_editor import XMLEditor


def get_kobo_data(dataset_id, auth_user, auth_passwd, host):
    url = "{}/{}/{}".format(host, "data", str(dataset_id))
    r = requests.get(url, auth=HTTPBasicAuth(auth_user, auth_passwd))
    return r.text


def post_kobo_data(auth_user, auth_passwd, host, f):
    url = "{}/{}".format(host, "submissions")
    files = {'xml_submission_file': open(f, 'rb')}
    r = requests.post(url, files=files, auth=HTTPBasicAuth(auth_user, auth_passwd))
    return r.text


host = "https://kc.kobotoolbox.org/api/v1/"
dataset_id = 83693
auth_user = "wcs_mtkb"
auth_passwd = "Gorilla2017"
new_form_id ="agtXX8E8PgfMieEsQXxkPX"
new_form_version = "vjZAttUZmTLuvtb6iarc87"

# get the kobo data

#kobo_data = json.loads(get_kobo_data(dataset_id, auth_user, auth_passwd, host))
with open('kobo_data.json') as f:
    kobo_data = json.load(f)


#writing kobo data to XML file

files = list()
j = 0
for d in kobo_data:

    file_name = "{}_{}.xml".format(new_form_id, j)
    files.append(file_name)
    print file_name

    editor = XMLEditor(file_name, formid=new_form_id, version=new_form_version)
    editor.formhub_uuid = d["formhub/uuid"]

    editor.welcome = d["welcome"]

    i = 0
    for hh_member in d["hhProfile/hhMembers"]:
        editor.hh_members.new()
        editor.hh_members[i].gender = hh_member["hhProfile/hhMembers/MemberGender"]
        editor.hh_members[i].birth = hh_member["hhProfile/hhMembers/MemberBirthYear"]
        i += 1


    editor.bns_matrix_big_credit_necessary = d["Credit/CreditNeed"]
    editor.bns_matrix_big_credit_possess = d["Credit/CreditHave"]

    try:
        if d["groupGPS/EnregistrerGPSmanuellement"] == "oui":
            editor.gps_method = "manual"
        else:
            editor.gps_method = "device"

        editor.lat = d["groupGPS/GPS_Y"]
        editor.long = d["groupGPS/GPS_X"]

    except KeyError:
        pass

    editor.instance_version = d["__version__"]
    editor.instance_id = d["meta/instanceID"]

    editor.finish()

    j += 1

# Upload all files to Kobo
for f in files:
    print post_kobo_data(auth_user, auth_passwd, host, f)
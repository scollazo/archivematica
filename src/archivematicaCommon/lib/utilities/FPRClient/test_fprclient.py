
import sys
import pytest
import vcr

import client
import getFromRestAPI

sys.path.append("/usr/share/archivematica/dashboard/")
from fpr import models
import main.models

# WARNING Rules must be refetched from the DB to get updated values

FPRSERVER = 'http://localhost:9000/fpr/api/v2/'


@pytest.fixture
def fprclient():
    """ FPRClient object, newly created for testing. """
    fpr_client = client.FPRClient(fprserver=FPRSERVER)
    assert fpr_client
    return fpr_client


@pytest.fixture
def idcommands():
    """ IDCommands that replace each other. """
    rule_a = {
        "replaces": None,
        "uuid": "1c7dd02f-dfd8-46cb-af68-5b305aea1d6e",
        "script": "script contents",
        "tool": None,
        "enabled": True,
        "script_type": "pythonScript",
        "config": "PUID",
        "description": "Rule A",
    }
    rule_b = {
        "replaces_id": "1c7dd02f-dfd8-46cb-af68-5b305aea1d6e",
        "uuid": "889a79ca-3964-409c-b943-40edc5d33f0f",
        "script": "script contents",
        "tool": None,
        "enabled": True,
        "script_type": "pythonScript",
        "config": "PUID",
        "description": "Rule B (replaces rule A, locally)",
    }
    rule_c = {
        "replaces_id": "889a79ca-3964-409c-b943-40edc5d33f0f",
        "uuid": "f73d72ef-6818-45ad-b351-fe0cdede9419",
        "script": "script contents",
        "tool": None,
        "enabled": True,
        "script_type": "pythonScript",
        "config": "PUID",
        "description": "Rule C (replaces rule B, locally)", # Could have been generated by replacing A
    }
    rule_a_fpr = {
        "replaces": None,
        "uuid": "1c7dd02f-dfd8-46cb-af68-5b305aea1d6e",
        "script": "script contents",
        "tool": None,
        "enabled": False,
        "script_type": "pythonScript",
        "config": "PUID",
        "description": "Rule A (from FPR)",
        "resource_uri": "/fpr/api/v2/id-command/1c7dd02f-dfd8-46cb-af68-5b305aea1d6e/",
        "lastmodified": "2011-9-18T18:31:29",
    }

    rule_r = {
        "replaces": "/fpr/api/v2/id-command/1c7dd02f-dfd8-46cb-af68-5b305aea1d6e/",
        "uuid": "e3ca565f-1cf9-4a6c-9732-70f7ed33a2fa",
        "script": "script contents",
        "tool": None,
        "enabled": True,
        "script_type": "pythonScript",
        "config": "PUID",
        "description": "Rule R (replaces A, from FPR)",
        "resource_uri": "/fpr/api/v2/id-command/e3ca565f-1cf9-4a6c-9732-70f7ed33a2fa/",
        "lastmodified": "2011-10-18T18:31:29",
    }
    return {
        "A": rule_a,
        "B": rule_b,
        "C": rule_c,
        "A-fpr": rule_a_fpr,
        "R": rule_r,
    }


@vcr.use_cassette("fixtures/vcr_cassettes/get_from_rest_api_id-commands.yaml")
def test_can_get_info_from_fprserver():
    """ Confirm the configured fprserver is accessible, and returns info. """
    params = {
        "format": "json",
        "limit": "0"
    }
    entries = getFromRestAPI._get_from_rest_api(url=FPRSERVER, resource='id-command', params=params, verbose=False, auth=None, verify=False)
    assert len(entries) == 2


@vcr.use_cassette("fixtures/vcr_cassettes/each_record_id-commands.yaml")
def test_can_fetch_records():
    records = list(getFromRestAPI.each_record("id-command", url=FPRSERVER))
    assert len(records) == 2


@pytest.mark.django_db
def test_insert_initial_chain(idcommands, fprclient):
    """ Insert a chain of rules into a new install. """
    # Use the FPR to add the first in a replacement chain
    # Initial rule in a chain should always be enabled
    fprclient.addResource(idcommands['A-fpr'], models.IDCommand)
    rule_a = models.IDCommand.objects.get(uuid=idcommands['A-fpr']['uuid'])
    assert rule_a.enabled == True
    assert rule_a.replaces == None

    # Use the FPR to add a replacement R for A
    fprclient.addResource(idcommands['R'], models.IDCommand)
    rule_a = models.IDCommand.objects.get(uuid=idcommands['A-fpr']['uuid'])
    rule_r = models.IDCommand.objects.get(uuid=idcommands['R']['uuid'])
    assert rule_a.enabled == False
    assert rule_r.enabled == True
    assert rule_r.replaces == rule_a


@pytest.mark.django_db
def test_add_replacement_rule_for_existing_rule(idcommands, fprclient):
    """ Insert a replacement rule for a rule that was not added via the fprclient. """
    # Insert initial rule A
    rule_a = models.IDCommand.objects.create(**idcommands['A'])
    assert rule_a.enabled == True
    assert rule_a.replaces == None
    # Use the FPR to add a replacement R for A
    fprclient.addResource(idcommands['R'], models.IDCommand)
    rule_a = models.IDCommand.objects.get(uuid=idcommands['A']['uuid'])
    rule_r = models.IDCommand.objects.get(uuid=idcommands['R']['uuid'])
    assert rule_a.enabled == False
    assert rule_a.replaces == None
    assert rule_r.enabled == True
    assert rule_r.replaces == rule_a


@pytest.mark.django_db
def test_replacement_of_manually_modified_rule(idcommands, fprclient):
    """ Insert a replacement rule for a rule that was locally modified. """
    # Initial setup: A <- B (active)
    # B replaced A
    # Insert from FPR rule R, replaces A
    # Result: A <- R <- B (active)

    # Insert initial rule A
    rule_a = models.IDCommand.objects.create(**idcommands['A'])
    assert rule_a.enabled == True
    assert rule_a.replaces == None

    # Insert rule B replacing A
    rule_b = models.IDCommand.objects.create(**idcommands['B'])
    rule_b.save(replacing=rule_a)
    rule_a = models.IDCommand.objects.get(uuid=idcommands['A']['uuid'])
    assert rule_a.enabled == False
    assert rule_a.replaces == None
    assert rule_b.enabled == True
    assert rule_b.replaces == rule_a

    # Use the FPR to add a replacement R for A
    fprclient.addResource(idcommands['R'], models.IDCommand)
    rule_a = models.IDCommand.objects.get(uuid=idcommands['A']['uuid'])
    rule_b = models.IDCommand.objects.get(uuid=idcommands['B']['uuid'])
    rule_r = models.IDCommand.objects.get(uuid=idcommands['R']['uuid'])
    assert rule_a.enabled == False
    assert rule_a.replaces == None
    assert rule_r.enabled == False
    assert rule_r.replaces == rule_a
    assert rule_b.enabled == True
    assert rule_b.replaces == rule_r


@pytest.mark.django_db
def test_updating_all_rules(fprclient):
    """ Test running the whole FPRClient autoupdate. """
    (status, response, exception) = fprclient.getUpdates()
    print status, response, exception
    assert status == 'success'
    assert 'Error' not in response
    assert exception is None
    # Check things were inserted into DB
    assert models.Format.objects.count() > 0
    assert models.FormatVersion.objects.count() > 0
    assert models.IDTool.objects.count() > 0
    assert models.IDCommand.objects.count() > 0
    assert models.IDRule.objects.count() > 0
    assert models.FPTool.objects.count() > 0
    assert models.FPCommand.objects.count() > 0
    assert models.FPRule.objects.count() > 0
    assert main.models.UnitVariable.objects.get(unittype='FPR', variable='maxLastUpdate') != "2000-01-01T00:00:00"

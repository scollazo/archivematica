#!/usr/bin/env python3
"""
Turn a dumpdata json into a Django data migration.

Parse a JSON file created by dumpdata and create a data migration using the Django ORM to bulk insert rows.

Usage: create_datamigration.py input_file.json output_file
"""
import json
import sys

if __name__ == '__main__':
    with open(sys.argv[1], 'r') as f:
        j = json.load(f)

    current_model = None
    with open(sys.argv[2], 'w') as f:
        for elem in j:
            if current_model != elem['model']:
                if current_model is not None:
                    print('    ])', file=f)
                    print('', file=f)
                current_model = elem['model']
                app, model = current_model.split('.')
                print('    %s = apps.get_model("%s", "%s")' % (model, app, model), file=f)
                print('    %s.objects.bulk_create([' % model, file=f)
            attr_str = ''
            attr_str += 'id="%s", ' % elem['pk']
            for k, v in elem['fields'].items():
                if isinstance(v, str):
                    if v and v[0] == "'":
                        v = ' ' + v
                    if v and v[-1] == "'":
                        v += ' '
                    temp = "%s=r'''%s''', " % (k, v)
                else:
                    temp = '%s=%s, ' % (k, v)
                attr_str += temp
            print('        %s(%s),' % (model, attr_str), file=f)
        print('    ])', file=f)
        print('', file=f)

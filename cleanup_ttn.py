from ApiAccess.TtnAccess import TtnAccess


ttn_full_acc_key ="ttn-key-here"
ttn_username = 'ttn-username-here'
    
ttn = TtnAccess(full_account_key=ttn_full_acc_key,username=ttn_username)
for app_id in ttn.get_application_ids():
    print(app_id)
    for enddevice_id in ttn.get_enddevice_ids_of_app(app_id=app_id):
        print("\t",enddevice_id)
        if 'delete-me' in app_id:
            ttn.delete_ttn_enddevice_from_app(app_id, enddevice_id)
    if 'delete-me' in app_id:
        ttn.delete_ttn_app(app_id)
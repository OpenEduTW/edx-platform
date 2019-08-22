###############################
Fcu edx-platform Documentation
###############################




Change History
**************
20190820:
    1. remove the grade-api page size
    2. add xuser into Django admin
    modified: 
        lms/djangoapps/school_id_login/admin.py
        lms/djangoapps/grades/api/v1/views.py

20190729:
    1. change the page size as 100
    modified:   
        lms/djangoapps/grades/api/v1/views.py

20190724:
    1. add page size setting for grade api
    modified:
        lms/djangoapps/grades/api/v1/views.py

20190708:
    1. add return uri field
    2. change the button style for nid
    3. add error page for nid
    modified:   
        lms/djangoapps/school_id_login/models.py
        lms/djangoapps/school_id_login/views.py
        lms/static/sass/views/_login-register.scss

    Add:
        lms/djangoapps/school_id_login/migrations/0003_xschools_return_uri.py
        lms/templates/school_id_login/

20190529:
    1. move client id to Django admin
modified:   
        lms/djangoapps/school_id_login/admin.py
	lms/djangoapps/school_id_login/models.py
        lms/djangoapps/school_id_login/views.py

    Add:
  	lms/djangoapps/school_id_login/migrations/0002_xschools.py

20190417:
    1. Remove useless code
    2. Remove the --end
    3. Change the NID as FCU_NID
    4. Add user/school check
    5. Add release note

    modified:
        common/djangoapps/student/models.py
	common/djangoapps/student/views/login.py
	lms/djangoapps/student_account/views.py
	lms/envs/common.py
	lms/static/js/student_account/views/account_settings_factory.js
	lms/static/js/student_account/views/account_settings_fields.js
	lms/templates/student_account/login.underscore
	lms/urls.py

    Add:
	docs/fcu_note.rst


20190430 
    1.add app 'school_id_login'

    modified:
        common/djangoapps/student/models.py
        common/djangoapps/student/views/login.py
        docs/fcu_note.rst
        lms/djangoapps/student_account/views.py
        lms/envs/aws.py
    
    Add:
	lms/djangoapps/school_id_login/


20190503
    1.move the method into app
    2.remove the register for FCU_NID
    3.remove the useless code

modified:   
        common/djangoapps/student/models.py
	common/djangoapps/student/views/login.py
	docs/fcu_note.rst
	lms/djangoapps/school_id_login/views.py
	lms/templates/student_account/register.underscore
	lms/urls.py




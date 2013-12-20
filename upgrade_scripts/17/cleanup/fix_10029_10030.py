import MySQLdb

mysql_host = 'localhost'
mysql_user = 'root'
mysql_pass = 'root'
mysql_db = 'skyline_dev'

mysql_con = MySQLdb.Connection(mysql_host, mysql_user, mysql_pass, mysql_db)
mysql_cur = mysql_con.cursor()

mysql_cur.execute('''update utilbill set rebill_id = null where id=620;''')
mysql_cur.execute('''update utilbill set rebill_id = null where id=644;''')
mysql_con.commit()

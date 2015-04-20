import argparse
from reebill.users import UserDAO

if __name__ == '__main__':
    # command-line arguments
    parser = argparse.ArgumentParser(
        description='Create and authenticate user accounts')
    parser.add_argument('command', choices=['add', 'check', 'change'],
                        help=('"add" to create a user, "check" to test authentication, '
                              '"change" to change password'))
    parser.add_argument('identifier')
    parser.add_argument('password')
    parser.add_argument('newpassword', nargs='?') # optional
    args = parser.parse_args()

    dao = UserDAO()

    if args.command == 'add':
        try:
            dao.create_user(args.identifier, args.password)
        except ValueError:
            print 'User "%s" already exists; use "change" to change password' \
                  % args.identifier
        else:
            print 'New user created'

    elif args.command == 'check':
        result = dao.load_user(args.identifier, args.password)
        if result is None:
            print 'Authentication failed'
        else:
            print 'Authentication succeeded'

    elif args.command == 'change':
        if args.newpassword is None:
            print 'New password must be specified'
            exit(1)
        result = dao.change_password(args.identifier, args.password,
                                     args.newpassword)
        if result:
            print 'Password changed'
        else:
            print 'Password change failed'

@click.command(name='create_tables')
@with_appcontext
def create_tables():
    db.create_all()
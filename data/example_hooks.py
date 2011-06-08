# hooks get two parameters, an alot.ui.UI object, and an alt.db.DBManager object
# for all commands X, pre_X gets called before, post_X after X is applied.

def pre_shutdown(ui,dbman):
    ui.logger.info('goodbye!')

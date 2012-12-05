var utilbills = db.utilbills.find({'end':null}).sort(['account']);

utilbills.forEach(function(u) {
    var reebill = db.reebills.findOne({'utilbills.id':u._id});
    if (reebill == null)
        return;
    if (reebill._id.sequence == 0)
        return;
    print(reebill._id.account + '-' + reebill._id.sequence);
});

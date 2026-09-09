frappe.ui.form.on('LC Shop', {
  setup(frm) {
    frm.set_query('warehouse', () => ({
      filters: {
        company: frm.doc.company || '',
        is_group: 0,
        disabled: 0,
      },
    }));
  },

  refresh(frm) {
    frm.toggle_enable('warehouse', Boolean(frm.doc.company));
  },

  company(frm) {
    frm.toggle_enable('warehouse', Boolean(frm.doc.company));
    return frm.set_value('warehouse', null);
  },
});

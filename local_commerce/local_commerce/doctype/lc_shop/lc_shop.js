frappe.ui.form.on('LC Shop', {
  setup(frm) {
    frm.set_query('warehouse', () => ({
      filters: {
        company: frm.doc.company || '',
        is_group: 0,
        disabled: 0,
      },
    }));
    frm.set_query('stock_adjustment_account', () => ({
      filters: {
        company: frm.doc.company || '',
        is_group: 0,
        disabled: 0,
        account_type: 'Stock Adjustment',
      },
    }));
    frm.set_query('cost_center', () => ({
      filters: {
        company: frm.doc.company || '',
        is_group: 0,
        disabled: 0,
      },
    }));
    frm.set_query('delivery_account', () => ({
      filters: {
        company: frm.doc.company || '',
        is_group: 0,
        disabled: 0,
      },
    }));
    frm.set_query('cod_cash_account', () => ({
      filters: {
        company: frm.doc.company || '',
        is_group: 0,
        disabled: 0,
        account_type: 'Cash',
      },
    }));
    frm.set_query('order_tax_template', () => ({
      filters: {
        company: frm.doc.company || '',
        disabled: 0,
      },
    }));
  },

  refresh(frm) {
    const enabled = Boolean(frm.doc.company);
    for (const field of ['warehouse', 'stock_adjustment_account', 'cost_center', 'delivery_account', 'cod_cash_account', 'order_tax_template']) {
      frm.toggle_enable(field, enabled);
    }
  },

  company(frm) {
    const enabled = Boolean(frm.doc.company);
    for (const field of ['warehouse', 'stock_adjustment_account', 'cost_center', 'delivery_account', 'cod_cash_account', 'order_tax_template']) {
      frm.toggle_enable(field, enabled);
    }
    return frm.set_value({
      warehouse: null,
      stock_adjustment_account: null,
      cost_center: null,
      delivery_account: null,
      order_tax_template: null,
      cod_cash_account: null,
    });
  },
});

function sync_shop_coordinate_pin(frm) {
  const latitude = frm.doc.latitude;
  const longitude = frm.doc.longitude;
  if (latitude == null || longitude == null || latitude === '' || longitude === '') return;
  return frm.set_value('location_map', JSON.stringify({
    type: 'FeatureCollection', features: [{ type: 'Feature', properties: {},
      geometry: { type: 'Point', coordinates: [Number(longitude), Number(latitude)] } }],
  }));
}

frappe.ui.form.on('LC Shop', {
  latitude(frm) { return sync_shop_coordinate_pin(frm); },
  longitude(frm) { return sync_shop_coordinate_pin(frm); },
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
    frm.set_query('fish_wastage_account', () => ({
      filters: { company: frm.doc.company || '', is_group: 0, disabled: 0, root_type: 'Expense' },
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
    const pricingAdmin = frappe.session.user === "Administrator" || frappe.user.has_role("LC Platform Administrator");
    for (const field of ["location_map", "latitude", "longitude", "address_line1", "city", "postal_code", "service_radius_km", "live_tracking_enabled"]) {
      frm.toggle_enable(field, pricingAdmin);
    }
    if (pricingAdmin && !frm.doc.location_map && (frm.doc.latitude || frm.doc.longitude)) {
      frm.set_value('location_map', JSON.stringify({
        type: 'FeatureCollection', features: [{ type: 'Feature', properties: {},
          geometry: { type: 'Point', coordinates: [frm.doc.longitude, frm.doc.latitude] } }],
      }));
    }
    for (const field of ["shop_type", "fish_wastage_account", "minimum_order_amount", "free_delivery_above", "delivery_fee", "delivery_fee_per_km", "delivery_included_km"]) {
      frm.toggle_enable(field, pricingAdmin);
    }
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
      fish_wastage_account: null,
      cost_center: null,
      delivery_account: null,
      order_tax_template: null,
      cod_cash_account: null,
    });
  },
});

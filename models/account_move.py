# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import xml.etree.ElementTree as ET
import base64
import re

class AccountMove(models.Model):
    _inherit = 'account.move'

    efaktur_nsfp = fields.Char(
        string='Nomor Seri Faktur Pajak (NSFP)',
        size=17,
        copy=False,
        tracking=True,
        help='Nomor Faktur Pajak 16 atau 17 digit resmi DJP'
    )
    coretax_trx_code = fields.Selection([
        ('01', '01 - Penyerahan BKP/JKP kepada Bukan Pemungut PPN'),
        ('02', '02 - Penyerahan kepada Pemungut Bendaharawan Pemerintah'),
        ('03', '03 - Penyerahan kepada Pemungut BUMN / Badan Usaha Tertentu'),
        ('04', '04 - DPP Nilai Lain'),
        ('07', '07 - PPN Tidak Dipungut (Kawasan Berikat/Kawasan Bebas)'),
        ('08', '08 - PPN Dibebaskan'),
        ('09', '09 - Penyerahan Aktiva Pasal 16D UU PPN'),
    ], string='Kode Transaksi Faktur', default='01', tracking=True)

    partner_npwp16 = fields.Char(
        string='NPWP / NIK (16 Digit)',
        compute='_compute_partner_npwp16',
        store=True,
        readonly=False,
        help='16 digit format NPWP Instansi/Badan atau NIK Perorangan'
    )
    
    is_retail_consumer = fields.Boolean(
        string='Konsumen Akhir (Tanpa NPWP)',
        default=False,
        help='Centang jika pembeli adalah konsumen akhir / perorangan tanpa NPWP/NIK (DJP: 0000000000000000)'
    )
    
    kmk_tax_rate = fields.Float(
        string='Kurs Pajak KMK (IDR)',
        digits=(12, 4),
        default=1.0,
        help='Kurs resmi Keputusan Menteri Keuangan (KMK) saat tanggal faktur untuk mata uang valas.'
    )

    coretax_status = fields.Selection([
        ('draft', 'Draft (Belum Diproses)'),
        ('ready', 'Siap Generate XML'),
        ('generated', 'XML Terbit (Siap Unggah Coretax)'),
        ('posted', 'Disetujui DJP (Valid & Terkunci)'),
        ('rejected', 'Ditolak DJP (Gagal)')
    ], string='Status Coretax DJP', default='draft', tracking=True, copy=False)

    coretax_xml_file = fields.Binary(string='File XML Coretax', readonly=True, copy=False)
    coretax_xml_filename = fields.Char(string='Nama File XML', copy=False)

    @api.depends('partner_id.vat', 'is_retail_consumer')
    def _compute_partner_npwp16(self):
        for move in self:
            if move.is_retail_consumer:
                move.partner_npwp16 = '0000000000000000'
            elif move.partner_id and move.partner_id.vat:
                cleaned_vat = ''.join(c for c in move.partner_id.vat if c.isdigit())
                if len(cleaned_vat) in (15, 16):
                    move.partner_npwp16 = cleaned_vat.zfill(16)
                else:
                    move.partner_npwp16 = False
            else:
                move.partner_npwp16 = False

    @api.constrains('efaktur_nsfp')
    def _check_nsfp_validity(self):
        for move in self:
            if move.efaktur_nsfp:
                clean_nsfp = ''.join(c for c in move.efaktur_nsfp if c.isdigit())
                if len(clean_nsfp) not in (16, 17):
                    raise ValidationError(_('Nomor Faktur Pajak Coretax harus 16 atau 17 digit angka!'))

    def _sanitize_xml_text(self, text, max_len=100):
        """Membersihkan karakter kontrol dan whitespace berlebih"""
        if not text:
            return '-'
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\n\r\t]', ' ', str(text)).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned[:max_len] if cleaned else '-'

    def action_generate_coretax_xml(self):
        """Generates Production-Grade Coretax XML conforming strictly to DJP TaxInvoiceBulk schema"""
        for move in self:
            # 1. State Guard & Lock Verification
            if move.state != 'posted':
                raise UserError(_('Faktur Pajak hanya dapat diterbitkan untuk Invoice yang sudah berstatus Posted!'))
            if move.coretax_status == 'posted':
                raise UserError(_('Faktur Pajak ini sudah berstatus Disetujui DJP dan terkunci dari perubahan!'))
            if move.move_type not in ('out_invoice', 'out_refund'):
                raise UserError(_('Modul Coretax hanya memproses Customer Invoice dan Customer Credit Note.'))
            
            # 2. Validasi Penjual (Company)
            if not move.company_id.vat:
                raise ValidationError(_('NPWP Perusahaan Anda (Company VAT) belum diisi di Settings Perusahaan.'))
            clean_company_vat = ''.join(c for c in move.company_id.vat if c.isdigit())
            if len(clean_company_vat) not in (15, 16):
                raise ValidationError(_('NPWP Perusahaan harus 15 atau 16 digit angka valid!'))
            seller_tin = clean_company_vat.zfill(16)

            # 3. Validasi Pembeli & NSFP
            if not move.efaktur_nsfp:
                raise ValidationError(_('Harap isi Nomor Seri Faktur Pajak (NSFP 16-17 digit) sebelum ekspor Coretax!'))
            if not move.partner_npwp16 and not move.is_retail_consumer:
                raise ValidationError(_('NPWP/NIK Pelanggan wajib diisi (atau centang Konsumen Akhir)!'))

            # 4. Validasi Baris Faktur
            valid_lines = move.invoice_line_ids.filtered(lambda l: not l.display_type and (l.price_subtotal or l.quantity))
            if not valid_lines:
                raise ValidationError(_('Invoice tidak memiliki baris barang/jasa yang valid untuk dilaporkan!'))

            # 5. Multi-Currency Kurs KMK Handling
            company_curr = move.company_id.currency_id
            invoice_curr = move.currency_id
            is_foreign = (invoice_curr != company_curr)
            
            rate_kmk = move.kmk_tax_rate if (is_foreign and move.kmk_tax_rate > 0) else 1.0

            # Build Root: TaxInvoiceBulk
            root = ET.Element('TaxInvoiceBulk')
            ET.SubElement(root, 'TIN').text = seller_tin
            
            list_of_invoices = ET.SubElement(root, 'ListOfTaxInvoice')
            invoice_elem = ET.SubElement(list_of_invoices, 'TaxInvoice')

            # Header Metadata (Reflects Normal vs Retur)
            invoice_date = move.invoice_date or fields.Date.today()
            ET.SubElement(invoice_elem, 'TaxInvoiceDate').text = invoice_date.strftime('%Y-%m-%d')
            invoice_opt = 'Retur' if move.move_type == 'out_refund' else 'Normal'
            ET.SubElement(invoice_elem, 'TaxInvoiceOpt').text = invoice_opt
            ET.SubElement(invoice_elem, 'TrxCode').text = move.coretax_trx_code
            ET.SubElement(invoice_elem, 'RefDesc').text = self._sanitize_xml_text(move.name, 50)

            # Buyer Information
            address_parts = [move.partner_id.street, move.partner_id.street2, move.partner_id.city]
            full_address = ', '.join([p for p in address_parts if p]) or '-'

            buyer_info = ET.SubElement(invoice_elem, 'BuyerInfo')
            buyer_tin = move.partner_npwp16 or '0000000000000000'
            ET.SubElement(buyer_info, 'BuyerTin').text = buyer_tin
            ET.SubElement(buyer_info, 'BuyerDocument').text = 'TIN' if buyer_tin != '0000000000000000' else 'NATIONAL_ID'
            ET.SubElement(buyer_info, 'BuyerCountry').text = 'IDN'
            buyer_name = 'Konsumen Akhir' if move.is_retail_consumer else (move.partner_id.name or 'Customer')
            ET.SubElement(buyer_info, 'BuyerName').text = self._sanitize_xml_text(buyer_name, 100)
            ET.SubElement(buyer_info, 'BuyerAdress').text = self._sanitize_xml_text(full_address, 100)
            ET.SubElement(buyer_info, 'BuyerEmail').text = self._sanitize_xml_text(move.partner_id.email, 100) if move.partner_id.email else ''
            ET.SubElement(buyer_info, 'BuyerIDTKU').text = '000000'

            # Line Items (ListOfGoodService)
            list_of_items = ET.SubElement(invoice_elem, 'ListOfGoodService')
            for line in valid_lines:
                item_elem = ET.SubElement(list_of_items, 'GoodService')
                ET.SubElement(item_elem, 'Opt').text = 'A'
                code_val = line.product_id.default_code or '000000'
                ET.SubElement(item_elem, 'Code').text = self._sanitize_xml_text(code_val, 20)
                name_val = line.name or line.product_id.name or 'Item'
                ET.SubElement(item_elem, 'Name').text = self._sanitize_xml_text(name_val, 100)
                ET.SubElement(item_elem, 'Unit').text = 'UM.0033'
                
                # Konversi ke Rupiah menggunakan Kurs KMK resmi
                price_unit = line.price_unit * rate_kmk if is_foreign else line.price_unit
                price_subtotal = line.price_subtotal * rate_kmk if is_foreign else line.price_subtotal
                
                # Pembulatan IDR Standar Akuntansi Odoo
                price_unit = company_curr.round(price_unit)
                price_subtotal = company_curr.round(price_subtotal)

                ET.SubElement(item_elem, 'Price').text = f"{price_unit:.2f}"
                ET.SubElement(item_elem, 'Qty').text = f"{line.quantity:.2f}"
                
                # Diskon Baris Terhitung
                discount_amount = company_curr.round((price_unit * line.quantity) * (line.discount / 100.0))
                ET.SubElement(item_elem, 'TotalDiscount').text = f"{discount_amount:.2f}"
                
                # Dasar Pengenaan Pajak (DPP)
                tax_base = price_subtotal
                ET.SubElement(item_elem, 'TaxBase').text = f"{tax_base:.2f}"
                ET.SubElement(item_elem, 'OtherTaxBase').text = '0.00'
                
                # Hitung PPN
                vat_rate = 0.0
                vat_amount = 0.0
                vat_taxes = line.tax_ids.filtered(lambda t: t.amount_type == 'percent' and t.amount > 0)
                if vat_taxes:
                    vat_rate = vat_taxes[0].amount
                    vat_amount = company_curr.round(tax_base * (vat_rate / 100.0))
                
                ET.SubElement(item_elem, 'VATRate').text = f"{vat_rate:.2f}"
                ET.SubElement(item_elem, 'VAT').text = f"{vat_amount:.2f}"
                ET.SubElement(item_elem, 'STLGRate').text = '0.00'
                ET.SubElement(item_elem, 'STLG').text = '0.00'

            # Serialization strictly with UTF-8 and double quotes
            xml_raw = ET.tostring(root, encoding='utf-8')
            xml_header = b'<?xml version="1.0" encoding="UTF-8"?>\n'
            full_xml_bytes = xml_header + xml_raw

            encoded_xml = base64.b64encode(full_xml_bytes)

            clean_nsfp = ''.join(c for c in move.efaktur_nsfp if c.isdigit())
            filename = f"Coretax_{clean_nsfp}_{invoice_date}.xml"
            
            # Write to Record
            move.write({
                'coretax_xml_file': encoded_xml,
                'coretax_xml_filename': filename,
                'coretax_status': 'generated'
            })
            
            # Create Official ir.attachment in Chatter for Enterprise Audit Trail
            self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': encoded_xml,
                'res_model': 'account.move',
                'res_id': move.id,
                'mimetype': 'application/xml'
            })
            
            move.message_post(body=f"Faktur Pajak Coretax XML ({filename}) berhasil diterbitkan dan tersimpan di berkas lampiran.")

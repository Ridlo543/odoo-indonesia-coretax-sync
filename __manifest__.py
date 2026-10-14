{
    'name': 'Indonesia e-Faktur Coretax DJP Sync & Automation',
    'version': '20.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Automated Indonesian e-Faktur Coretax XML Generator & NSFP Compliance',
    'description': """
        Enterprise Odoo 20.0 & 19.0 module for Indonesian Coretax DJP Compliance:
        - Inherits account.move (Customer Invoices)
        - Accommodates 16-digit NPWP / NIK Validation (PMK 112/2022)
        - Automated Multi-Currency to IDR conversion
        - 1-Click Coretax DJP XML Generator (TaxInvoiceBulk Schema)
        - Audit trail & NSFP lifecycle tracking
    """,
    'author': 'Ridlo Abdullah Ulinnuha',
    'depends': ['account', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

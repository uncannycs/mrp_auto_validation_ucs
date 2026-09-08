# -*- coding: utf-8 -*-

{
    'name': 'Manufacturing Order Auto Confirmation | MRP Order Auto Confirmation | Smart MO Processing | Auto Process MO | Auto Process Manufacturing Orders',
    'version': '19.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Auto Confirm Manufacturing Order Auto Process MO Auto Validate MRP Order Process Work Orders Automatically',
    'description': """
Auto Process Manufacturing Order Odoo App is designed to automate the manufacturing process by enabling the automatic confirmation of manufacturing orders. This app eliminates the need for manual intervention in the confirmation process. By auto-validating manufacturing orders, businesses can save time, improve operational efficiency, and focus on other critical areas of production management. It is particularly beneficial for companies with high-volume manufacturing processes, as it ensures that orders are confirmed promptly and production can proceed without interruptions.

Features:
- Auto Process Manufacturing Order by single click.
- Option for Available Quantity processing or Forcefully Done processing.
- Automatically confirm manufacturing orders, update deliveries, process work orders, and post inventory/journals.
- Raises warning if selected manufacturing order is not in draft stage.
    """,
    'depends': ['base', 'mrp', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/auto_confirm_mrp_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'website': 'https://uncannycs.com',
    'author': 'Uncanny Consulting Services LLP',
    'maintainer': 'Uncanny Consulting Services LLP',
    'license': 'Other proprietary',
    "images": ['static/description/banner.gif'],
    "price": 50,
    "currency": "USD",
}

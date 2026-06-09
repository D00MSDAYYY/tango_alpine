from PySide6.QtWidgets import QDialog

from aux.gui.widgets.opener_dialog import OpenerDialog
from aux.gui.widgets.searchable_list import SearchableListView


class ChannelPicker:
    def pick_channels(self, channel_settings, existing_channels) -> list:
        existing_names = {cnl.settings.name for cnl in existing_channels}
        list_view = SearchableListView(
            items=channel_settings,
            item_maker=lambda cnl_sett: f"{cnl_sett.name}",
            multi_select=True,
        )
        dialog = OpenerDialog(list_view)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return []
        return [
            sett
            for sett in list_view.get_selected_data()
            if sett.name not in existing_names
        ]

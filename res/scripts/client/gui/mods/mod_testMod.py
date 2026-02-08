import os
import json
import BigWorld
import Keys

from gui import InputHandler, SystemMessages

from CurrentVehicle import g_currentVehicle
from helpers import dependency
from skeletons.gui.shared import IItemsCache
from skeletons.gui.shared.utils import IHangarSpace
from skeletons.gui.customization import ICustomizationService
from items.components.c11n_constants import SeasonType, CustomizationType
from items import makeIntCompactDescrByID
from items.customizations import isEditedStyle
from gui.Scaleform.daapi.view.lobby.customization.shared import removePartsFromOutfit

STYLE_ID = 31438

def apply_customization(item_inv_id, customization_data):
    BigWorld.player().shop.buyAndEquipOutfit(item_inv_id, customization_data, None)

def remove_customization(item_inv_id):
    BigWorld.player().shop.buyAndEquipOutfit(item_inv_id, [(b'', 15)], None)

def get_vehicle_customization_data(vehicle):
    items_cache = dependency.instance(IItemsCache)
    vehicle_cd = vehicle.descriptor.makeCompactDescr()
    
    data = []
    for season in SeasonType.COMMON_SEASONS:
        outfit = vehicle.getOutfit(season)
        if not outfit:
            data.append((b'', season))
            continue
            
        component = outfit.pack()
        if component.styleId:
            int_cd = makeIntCompactDescrByID('customizationItem', CustomizationType.STYLE, component.styleId)
            style = items_cache.items.getItemByCD(int_cd)
            if style:
                base_outfit = removePartsFromOutfit(season, style.getOutfit(season, vehicle_cd))
                component = component.getDiff(base_outfit.pack())
            
        data.append((component.makeCompDescr(), season))

    return data

def get_style_customization_data(style_id, vehicle):
    from vehicle_outfit.outfit import Outfit
    outfit = Outfit(vehicleCD=vehicle.descriptor.makeCompactDescr())
    
    component = outfit.pack()
    component.styleId = style_id
    
    encoded = component.makeCompDescr()
    return [(encoded, season) for season in SeasonType.COMMON_SEASONS]

def get_style_item_by_id(style_id):
    items_cache = dependency.instance(IItemsCache)      
    int_cd = makeIntCompactDescrByID('customizationItem', CustomizationType.STYLE, style_id)

    style_item = items_cache.items.getItemByCD(int_cd)
    return style_item

def is_style_already_set(style_item):
    items_cache = dependency.instance(IItemsCache)
    current_vehicle = g_currentVehicle.item
    
    installed_vehicles = style_item.getInstalledVehicles()
    if installed_vehicles:
        for vehicle_cd in installed_vehicles:
            vehicle = items_cache.items.getItemByCD(vehicle_cd)
            if vehicle and vehicle.invID == current_vehicle.invID:
                return True

    return False

def is_style_available(style_item):
    items_cache = dependency.instance(IItemsCache)
    current_vehicle = g_currentVehicle.item

    if style_item.inventoryCount > 0:
        return True, None
    
    installed_vehicles = style_item.getInstalledVehicles()
    if installed_vehicles:
        for vehicle_cd in installed_vehicles:
            vehicle = items_cache.items.getItemByCD(vehicle_cd)
            return not vehicle.isLocked, vehicle

    return False, None

class BatyaMod(object):
    hangarSpace = dependency.descriptor(IHangarSpace)

    def __init__(self):
        self.__conf_dir = os.path.join('mods', 'configs', 'BatyaMod')
        self.__conf_file = os.path.join(self.__conf_dir, 'saved_info.json')
        self.__data = {
            'active': False,
            'profiles': {} # Dict: { "Nickname": { "vehIntCD": "hex_data" } }
        }
        self.__load_config()

        self.hangarSpace.onSpaceCreate += self.__add_listeners
        self.hangarSpace.onSpaceDestroy += self.__remove_listeners

        # Если мод загружен, когда ангар уже инициализирован
        if self.hangarSpace.spaceInited:
            self.__add_listeners()

    def __add_listeners(self):
        InputHandler.g_instance.onKeyDown += self.handle_key_event

    def __remove_listeners(self):
        InputHandler.g_instance.onKeyDown -= self.handle_key_event
        
    def __load_config(self):
        if not os.path.exists(self.__conf_dir):
            os.makedirs(self.__conf_dir)
        if os.path.exists(self.__conf_file):
            try:
                with open(self.__conf_file, 'r') as f:
                    self.__data = json.load(f)
            except Exception as e:
                print("Error loading config: %s" % str(e))
        else:
            self.__save_config()

    def __save_config(self):
        try:
            with open(self.__conf_file, 'w') as f:
                json.dump(self.__data, f, indent=4)
        except Exception as e:
            print("Error saving config: %s" % str(e))

    def __push_msg(self, text, header="BatyaMod"):
        SystemMessages.pushMessage(text, SystemMessages.SM_TYPE.InformationHeader, messageData={'header': header})

    def handle_key_event(self, event):
        if event.isKeyDown():
            if event.key == Keys.KEY_F9:
                self.__data['active'] = not self.__data['active']
                status = "ON" if self.__data['active'] else "OFF"
                self.__push_msg("Статус: %s" % status)
                self.__save_config()

            if event.key == Keys.KEY_F10:
                if self.__data['active']:
                    self.__process_style_logic()
                else:
                    self.__push_msg("Мод выключен, нажмите F9 чтобы включить.")

    def __process_style_logic(self):
        vehicle = g_currentVehicle.item
        if not vehicle or not vehicle.isInInventory:
            self.__push_msg("Танчик не выбран!")
            return

        style_item = get_style_item_by_id(STYLE_ID)
        if not style_item:
            self.__push_msg("Запрашиваемый стиль не существует!")
            return
        
        if is_style_already_set(style_item):
            self.__push_msg("Запрашиваемый стиль уже установлен на танк!")
            return
        
        style_available, vehicle = is_style_available(style_item)
        if not style_available:
            self.__push_msg("Запрашиваемый стиль недоступен!")
            return
        
        player_name = BigWorld.player().name

        if vehicle:
            #self.__push_msg("Снимаем запрашиваемый стиль!")
            remove_customization(vehicle.invID)

            profile = self.__data['profiles'].get(player_name, {})
            saved_hex_data = profile.get(str(vehicle.invID))

            if saved_hex_data:
                request_data = [ (d.decode('hex'), s) for d, s in saved_hex_data ]
                apply_customization(vehicle.invID, request_data)
    
        current_outfit_data = get_vehicle_customization_data(g_currentVehicle.item)
        
        serialized_data = []
        for b_data, season in current_outfit_data:
            serialized_data.append((b_data.encode('hex'), season))

        if player_name not in self.__data['profiles']:
            self.__data['profiles'][player_name] = {}
        
        self.__data['profiles'][player_name][str(g_currentVehicle.item.invID)] = serialized_data
        self.__save_config()

        remove_customization(g_currentVehicle.item.invID)

        def final_step():
            style_data = get_style_customization_data(STYLE_ID, g_currentVehicle.item)
            apply_customization(g_currentVehicle.item.invID, style_data)
            #self.__push_msg("Стиль применен!")

        BigWorld.callback(0.1, final_step)

batyaMod = BatyaMod()
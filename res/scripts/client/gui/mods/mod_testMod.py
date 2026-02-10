import os
import json
import BigWorld
import Keys

from gui import InputHandler, SystemMessages

from PlayerEvents import g_playerEvents
from CurrentVehicle import g_currentVehicle
from helpers import dependency
from skeletons.gui.shared import IItemsCache
from skeletons.gui.shared.utils import IHangarSpace
from skeletons.gui.customization import ICustomizationService
from items.components.c11n_constants import SeasonType, CustomizationType
from items import makeIntCompactDescrByID
from items.customizations import isEditedStyle
from gui.Scaleform.daapi.view.lobby.customization.shared import removePartsFromOutfit

from constants import QUEUE_TYPE

from gui.game_control.platoon_controller import PlatoonController
from gui.prb_control.entities.base.pre_queue.entity import PreQueueEntity

STYLE_ID = 31438

def apply_customization(item_inv_id, customization_data):
    BigWorld.player().shop.buyAndEquipOutfit(item_inv_id, customization_data, None)

def remove_customization(item_inv_id):
    BigWorld.player().shop.buyAndEquipOutfit(item_inv_id, [(b'', 15)], None)

def get_vehicle_customization_data(vehicle):
    itemsCache = dependency.instance(IItemsCache)
    c11nService = dependency.instance(ICustomizationService)
    
    requestData = []
    vehicleCD = vehicle.descriptor.makeCompactDescr()

    for season in SeasonType.COMMON_SEASONS:
        outfit = vehicle.getOutfit(season)
        if not outfit:
            requestData.append((b'', season))
            continue

        if outfit.id:
            intCD = makeIntCompactDescrByID('customizationItem', CustomizationType.STYLE, outfit.id)
            style = itemsCache.items.getItemByCD(intCD)
            
            outfit = removePartsFromOutfit(season, outfit)
            
            if style and style.isProgressive:
                outfit = c11nService.removeAdditionalProgressionData(
                    outfit=outfit, style=style, vehCD=vehicleCD, season=season
                )

        component = outfit.pack()
        
        if component.styleId and isEditedStyle(component):
            intCD = makeIntCompactDescrByID('customizationItem', CustomizationType.STYLE, component.styleId)
            style = itemsCache.items.getItemByCD(intCD)
            
            baseOutfit = removePartsFromOutfit(season, style.getOutfit(season, vehicleCD))
            if style.isProgressive:
                baseOutfit = c11nService.removeAdditionalProgressionData(
                    outfit=baseOutfit, style=style, vehCD=vehicleCD, season=season
                )
            
            baseComponent = baseOutfit.pack()
            component = component.getDiff(baseComponent)

        requestData.append((component.makeCompDescr(), season))

    return requestData

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
        self.__add_listeners()

        self.__install_platoon_toggle_hook()
        self.__install_prequeue_hook()

    def __add_listeners(self):
        InputHandler.g_instance.onKeyDown += self.handle_key_event

    def __install_platoon_toggle_hook(self):
        if not hasattr(PlatoonController, '_batya_toggle_orig'):
            PlatoonController._batya_toggle_orig = PlatoonController.togglePlayerReadyAction
            
            def _hook(self_pc, *a, **kw):
                if not self_pc.prbEntity.getPlayerInfo().isReady:
                    if self_pc.getQueueType() == QUEUE_TYPE.RANDOMS:
                        if self.hangarSpace.spaceInited and self.__data['active']:
                            self.__process_style_logic()

                return PlatoonController._batya_toggle_orig(self_pc, *a, **kw)
            
            PlatoonController.togglePlayerReadyAction = _hook

    def __install_prequeue_hook(self):
        if not hasattr(PreQueueEntity, '_batya_prequeue_orig'):
            PreQueueEntity._batya_prequeue_orig = PreQueueEntity.queue
            
            def _hook(self_pqe, ctx, callback=None):
                if self_pqe.getQueueType() == QUEUE_TYPE.RANDOMS:
                    if self.hangarSpace.spaceInited and self.__data['active']:
                        self.__process_style_logic()

                return PreQueueEntity._batya_prequeue_orig(self_pqe, ctx, callback)
            
            PreQueueEntity.queue = _hook
        
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
                status = "Автоприменение вкл" if self.__data['active'] else "Автоприменение выкл"
                self.__push_msg("Статус: %s" % status)
                self.__save_config()

            elif event.key == Keys.KEY_F10 and self.hangarSpace.spaceInited:
                self.__process_style_logic()

    def __process_style_logic(self):
        current_vehicle = g_currentVehicle.item
        if not current_vehicle or not current_vehicle.isInInventory:
            self.__push_msg("Танчик не выбран!")
            return

        if current_vehicle.isLocked:
            self.__push_msg("Танчик заблокирован!")
            return

        style_item = get_style_item_by_id(STYLE_ID)
        if not style_item:
            self.__push_msg("Запрашиваемый стиль не существует!")
            return
        
        if is_style_already_set(style_item):
            #self.__push_msg("Запрашиваемый стиль уже установлен на танк!")
            return
        
        if current_vehicle.isOutfitLocked or not style_item.mayInstall(current_vehicle):
            #self.__push_msg("Установка стиля на выбранный танк невозможна!")
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
    
        current_outfit_data = get_vehicle_customization_data(current_vehicle)
        remove_customization(current_vehicle.invID)

        def final_step():
            style_data = get_style_customization_data(STYLE_ID, current_vehicle)
            apply_customization(current_vehicle.invID, style_data)
            #self.__push_msg("Стиль применен!")

        BigWorld.callback(0.0, final_step)

        serialized_data = []
        for b_data, season in current_outfit_data:
            serialized_data.append((b_data.encode('hex'), season))

        if player_name not in self.__data['profiles']:
            self.__data['profiles'][player_name] = {}
        
        self.__data['profiles'][player_name][str(g_currentVehicle.item.invID)] = serialized_data
        self.__save_config()

batyaMod = BatyaMod()
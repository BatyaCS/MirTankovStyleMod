import BigWorld

from CurrentVehicle import g_currentVehicle
from helpers import dependency
from skeletons.gui.shared import IItemsCache
from skeletons.gui.shared.utils import IHangarSpace
from skeletons.gui.customization import ICustomizationService
from items.components.c11n_constants import SeasonType, CustomizationType
from items import makeIntCompactDescrByID
from items.customizations import isEditedStyle
from gui.Scaleform.daapi.view.lobby.customization.shared import removePartsFromOutfit

from test_mod.settings import STYLE_ID
from test_mod.logger import log

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

def restyle_test():
    vehicle = g_currentVehicle.item
    if not vehicle or not vehicle.isInInventory:
        log("Танчик не выбран!")
        return

    style_item = get_style_item_by_id(STYLE_ID)
    if not style_item:
        log("Запрашиваемый стиль не существует!")
        return
    
    if is_style_already_set(style_item):
        log("Запрашиваемый стиль уже установлен на танк!")
        return
    
    style_available, vehicle = is_style_available(style_item)
    if not style_available:
        log("Запрашиваемый стиль недоступен!")
        return
    
    if vehicle:
        log("Снимаем запрашиваемый стиль!")
        remove_customization(vehicle.invID)

    current_vehicle_customization = get_vehicle_customization_data(g_currentVehicle.item)
    def step_clear_current():
        remove_customization(g_currentVehicle.item.invID)

        def step_apply_required():
            log("Применяем запрашиваемый стиль!")
            apply_customization(g_currentVehicle.item.invID, get_style_customization_data(STYLE_ID, g_currentVehicle.item))

            def step_restore_current():
                log("Возвращаем старый камик!")
                BigWorld.callback(0.0, lambda: apply_customization(g_currentVehicle.item.invID, current_vehicle_customization))

            BigWorld.callback(3.0, step_restore_current)
            
        BigWorld.callback(0.5, step_apply_required)

    BigWorld.callback(0.5, step_clear_current)

hangarSpace = dependency.instance(IHangarSpace) # type: IHangarSpace

def init():
  hangarSpace.onVehicleChanged += onHangarVehicleChanged

import os

def onHangarVehicleChanged():
  log(os.getcwd())
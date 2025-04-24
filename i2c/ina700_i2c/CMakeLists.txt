add_executable(ina700_i2c
        ina700_i2c.c
        )

# pull in common dependencies and additional i2c hardware support
target_link_libraries(ina700_i2c pico_stdlib hardware_i2c)

# create map/bin/hex file etc.
pico_add_extra_outputs(ina700_i2c)

# add url via pico_set_program_url
example_auto_set_url(ina700_i2c)

pico_enable_stdio_usb(ina700_i2c 1)
pico_enable_stdio_uart(ina700_i2c 0)


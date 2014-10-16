<?xml version="1.0" encoding="UTF-8"?>
<structure version="9" htmlmode="strict" relativeto="*SPS" encodinghtml="UTF-8" encodingrtf="ISO-8859-1" encodingpdf="UTF-8" useimportschema="1" embed-images="1">
	<parameters/>
	<schemasources>
		<namespaces>
			<nspair prefix="sb" uri="skylinebill"/>
			<nspair prefix="ub" uri="utilitybill"/>
		</namespaces>
		<schemasources>
			<xsdschemasource name="XML" main="1" schemafile="C:\workspace-skyline\billing\UtilityBill.xsd" workingxmlfile="C:\workspace-skyline\billing\sample\PECO-94443-01819-2009100609.xml">
				<xmltablesupport/>
				<textstateicons/>
			</xsdschemasource>
		</schemasources>
	</schemasources>
	<modules/>
	<flags>
		<scripts/>
		<globalparts/>
		<designfragments/>
		<pagelayouts/>
	</flags>
	<scripts>
		<script language="javascript"/>
	</scripts>
	<importedxslt/>
	<globalstyles/>
	<mainparts>
		<children>
			<globaltemplate subtype="main" match="/">
				<children>
					<documentsection>
						<properties columncount="1" columngap="0.50in" headerfooterheight="fixed" pagemultiplepages="0" pagenumberingformat="1" pagenumberingstartat="auto" pagestart="next" paperheight="11in" papermarginbottom="0.79in" papermarginfooter="0.30in" papermarginheader="0.30in" papermarginleft="0.60in" papermarginright="0.60in" papermargintop="0.79in" paperwidth="8.50in"/>
					</documentsection>
					<template subtype="source" match="XML">
						<children>
							<paragraph paragraphtag="h2">
								<children>
									<text fixtext="Skyline Measurement"/>
								</children>
							</paragraph>
							<paragraph paragraphtag="h2">
								<children>
									<text fixtext="Utility Measurement"/>
								</children>
							</paragraph>
							<newline/>
							<paragraph paragraphtag="h2">
								<children>
									<text fixtext="Aggregated Measurement"/>
								</children>
							</paragraph>
							<template subtype="element" groupingtype="group-by" groupingmatch="ub:measuredusage/@service" match="ub:utilitybill">
								<sort>
									<key match="current-grouping-key()"/>
								</sort>
								<children>
									<template subtype="userdefined" match="current-group()">
										<children>
											<tgrid>
												<properties border="1"/>
												<children>
													<tgridbody-cols>
														<children>
															<tgridcol/>
															<tgridcol/>
															<tgridcol/>
														</children>
													</tgridbody-cols>
													<tgridheader-rows>
														<children>
															<tgridrow>
																<children>
																	<tgridcell>
																		<children>
																			<text fixtext="service"/>
																		</children>
																	</tgridcell>
																	<tgridcell>
																		<children>
																			<text fixtext="meter"/>
																		</children>
																	</tgridcell>
																	<tgridcell/>
																</children>
															</tgridrow>
														</children>
													</tgridheader-rows>
													<tgridbody-rows>
														<children>
															<template subtype="element" match="ub:measuredusage">
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<template subtype="attribute" match="service">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" groupingtype="group-by" groupingmatch="@shadow" match="ub:meter">
																						<sort>
																							<key match="current-grouping-key()"/>
																						</sort>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell/>
																		</children>
																	</tgridrow>
																</children>
																<variables/>
															</template>
														</children>
													</tgridbody-rows>
												</children>
											</tgrid>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<newline/>
							<newline/>
							<template subtype="element" match="ub:utilitybill">
								<children>
									<template subtype="element" match="ub:measuredusage">
										<children>
											<template subtype="element" match="ub:meter">
												<children>
													<template subtype="element" match="ub:register">
														<children>
															<template subtype="element" groupingtype="group-by" groupingmatch="../ub:identifier" match="ub:total">
																<sort>
																	<key match="current-grouping-key()"/>
																</sort>
																<children>
																	<template subtype="userdefined" match="current-group()">
																		<children>
																			<content>
																				<format datatype="decimal"/>
																			</content>
																		</children>
																		<variables/>
																	</template>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<newline/>
							<newline/>
							<template subtype="element" match="ub:utilitybill">
								<children>
									<template subtype="element" groupingtype="group-by" groupingmatch="@service" match="ub:measuredusage">
										<sort>
											<key match="current-grouping-key()"/>
										</sort>
										<children>
											<tgrid>
												<properties border="1"/>
												<children>
													<tgridbody-cols>
														<children>
															<tgridcol/>
															<tgridcol/>
														</children>
													</tgridbody-cols>
													<tgridheader-rows>
														<children>
															<tgridrow>
																<children>
																	<tgridcell/>
																	<tgridcell/>
																</children>
															</tgridrow>
														</children>
													</tgridheader-rows>
													<tgridbody-rows>
														<children>
															<template subtype="userdefined" match="current-group()">
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<template subtype="attribute" match="service">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" groupingtype="group-by" groupingmatch="ub:identifier" match="ub:meter">
																						<sort>
																							<key match="current-grouping-key()"/>
																						</sort>
																						<children>
																							<tgrid>
																								<properties border="1"/>
																								<children>
																									<tgridbody-cols>
																										<children>
																											<tgridcol/>
																											<tgridcol/>
																											<tgridcol/>
																										</children>
																									</tgridbody-cols>
																									<tgridheader-rows>
																										<children>
																											<tgridrow>
																												<children>
																													<tgridcell/>
																													<tgridcell/>
																													<tgridcell/>
																												</children>
																											</tgridrow>
																										</children>
																									</tgridheader-rows>
																									<tgridbody-rows>
																										<children>
																											<template subtype="userdefined" match="current-group()">
																												<children>
																													<tgridrow>
																														<children>
																															<tgridcell>
																																<children>
																																	<template subtype="element" match="ub:identifier">
																																		<children>
																																			<content/>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																															</tgridcell>
																															<tgridcell>
																																<children>
																																	<template subtype="attribute" match="shadow">
																																		<children>
																																			<content/>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																															</tgridcell>
																															<tgridcell>
																																<children>
																																	<tgrid>
																																		<properties border="1"/>
																																		<children>
																																			<tgridbody-cols>
																																				<children>
																																					<tgridcol/>
																																					<tgridcol/>
																																					<tgridcol/>
																																					<tgridcol/>
																																					<tgridcol/>
																																					<tgridcol/>
																																					<tgridcol/>
																																				</children>
																																			</tgridbody-cols>
																																			<tgridheader-rows>
																																				<children>
																																					<tgridrow>
																																						<children>
																																							<tgridcell>
																																								<children>
																																									<text fixtext="identifier"/>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<children>
																																									<text fixtext="description"/>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<children>
																																									<text fixtext="units"/>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<children>
																																									<text fixtext="priorreading"/>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<children>
																																									<text fixtext="presentreading"/>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<children>
																																									<text fixtext="factor"/>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<children>
																																									<text fixtext="total"/>
																																								</children>
																																							</tgridcell>
																																						</children>
																																					</tgridrow>
																																				</children>
																																			</tgridheader-rows>
																																			<tgridbody-rows>
																																				<children>
																																					<template subtype="element" match="ub:register">
																																						<children>
																																							<tgridrow>
																																								<children>
																																									<tgridcell>
																																										<children>
																																											<template subtype="element" match="ub:identifier">
																																												<children>
																																													<content/>
																																												</children>
																																												<variables/>
																																											</template>
																																										</children>
																																									</tgridcell>
																																									<tgridcell>
																																										<children>
																																											<template subtype="element" match="ub:description">
																																												<children>
																																													<content/>
																																												</children>
																																												<variables/>
																																											</template>
																																										</children>
																																									</tgridcell>
																																									<tgridcell>
																																										<children>
																																											<template subtype="element" match="ub:units">
																																												<children>
																																													<content/>
																																												</children>
																																												<variables/>
																																											</template>
																																										</children>
																																									</tgridcell>
																																									<tgridcell>
																																										<children>
																																											<template subtype="element" match="ub:priorreading">
																																												<children>
																																													<content>
																																														<format datatype="decimal"/>
																																													</content>
																																												</children>
																																												<variables/>
																																											</template>
																																										</children>
																																									</tgridcell>
																																									<tgridcell>
																																										<children>
																																											<template subtype="element" match="ub:presentreading">
																																												<children>
																																													<content>
																																														<format datatype="decimal"/>
																																													</content>
																																												</children>
																																												<variables/>
																																											</template>
																																										</children>
																																									</tgridcell>
																																									<tgridcell>
																																										<children>
																																											<template subtype="element" match="ub:factor">
																																												<children>
																																													<content>
																																														<format datatype="integer"/>
																																													</content>
																																												</children>
																																												<variables/>
																																											</template>
																																										</children>
																																									</tgridcell>
																																									<tgridcell>
																																										<children>
																																											<template subtype="element" match="ub:total">
																																												<children>
																																													<content>
																																														<format datatype="decimal"/>
																																													</content>
																																												</children>
																																												<variables/>
																																											</template>
																																										</children>
																																									</tgridcell>
																																								</children>
																																							</tgridrow>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridbody-rows>
																																		</children>
																																	</tgrid>
																																</children>
																															</tgridcell>
																														</children>
																													</tgridrow>
																												</children>
																												<variables/>
																											</template>
																										</children>
																									</tgridbody-rows>
																								</children>
																							</tgrid>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
																<variables/>
															</template>
														</children>
													</tgridbody-rows>
												</children>
											</tgrid>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<newline/>
						</children>
						<variables/>
					</template>
				</children>
			</globaltemplate>
		</children>
	</mainparts>
	<globalparts/>
	<pagelayout>
		<properties paperheight="11.69in" paperwidth="8.27in"/>
	</pagelayout>
	<designfragments/>
</structure>

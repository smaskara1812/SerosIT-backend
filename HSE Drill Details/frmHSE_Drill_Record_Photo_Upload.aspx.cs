using System;
using System.Data;
using System.Configuration;
using System.Collections;
using System.Web;
using System.Web.Security;
using System.Web.UI;
using System.Web.UI.WebControls;
using System.Web.UI.WebControls.WebParts;
using System.Web.UI.HtmlControls;
using System.Data.SqlClient;
using EBS.Classes;
using EBS_Common.Classes.Misc;
using EBS_Common.Classes;
using System.Collections.Generic;

public partial class Quality_And_Safety_frmHSE_Drill_Record_Photo_Upload : System.Web.UI.Page
{
    # region User defined variables
    //protected Common_DataRetrival _Common_DataRetrival;
    string strConString = "";
    protected DataSet Ds;
    string ErrorString = "";
    SqlConnection Conn;
    SqlDataAdapter Da;
    int intUser_Id;
    Button[] btnEnableDisable;
    Int16 intMenu_id;
    #endregion

    protected void Page_Load(object sender, EventArgs e)
    {        
        # region Code to Enable / Disable Button
        #region Adding buttons which needs to pass
        var list = new List<Button>();
        //list.Add(btnSearch);

        btnEnableDisable = list.ToArray();
        #endregion

        strConString = ConfigurationManager.ConnectionStrings["provider_default"].ToString();

        #region 1st Parameter is always Menu Id
        string strScramble = Request.QueryString["A"];
        string strdeCrypt = clsMiscellaneous.decryptQueryString(strScramble.Replace(" ", "+"));

        string strMonthly_HSE_Returns_Hdr_Id = Request.QueryString["B"];///Copy the HDR ID in this
        tbDrill_Record_Hdr_Id_Hidden.Value = clsMiscellaneous.decryptQueryString(strMonthly_HSE_Returns_Hdr_Id.Replace(" ", "+"));

        intMenu_id = Convert.ToInt16(strdeCrypt);
        intUser_Id = Convert.ToInt16(Session["User_Id"].ToString());

        # endregion

        if (!IsPostBack)
        {
            EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Add");

            FillGrid();
            tbPostbackFlag_Hidden.Value = ""; 
        }
        
        if (tbPostbackFlag_Hidden.Value == "SEARCH")
        {
            FillGrid();
            tbPostbackFlag_Hidden.Value = ""; 
        }
        #endregion
    }


    protected void FillGrid()
    {
        ClearMe(false);

        EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Search");

        Conn = new SqlConnection(strConString);
        try
        {
            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Def + "Prc_HSE_Drill_Record_Photo_Upload", Conn);
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;
            Da.SelectCommand.Parameters.Add("@Drill_Record_Hdr_Id", SqlDbType.SmallInt).Value = Convert.ToInt16(tbDrill_Record_Hdr_Id_Hidden.Value);
            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Select_By_Drill_Record_Hdr_Id";
            Da.Fill(Ds, "DataForEdit");

           
            DataTable contacts = Ds.Tables["DataForEdit"];
            if (contacts.Rows.Count > 0)
            {
                grdContact.DataSource = contacts;
                grdContact.DataBind();

            }
            else
            {
                contacts.Rows.Add(contacts.NewRow());
                grdContact.DataSource = contacts;
                grdContact.DataBind();

                int TotalColumns = grdContact.Rows[0].Cells.Count;
                grdContact.Rows[0].Cells.Clear();
                grdContact.Rows[0].Cells.Add(new TableCell());
                grdContact.Rows[0].Cells[0].ColumnSpan = TotalColumns;
                grdContact.Rows[0].Cells[0].Text = "No Record Found";
            }
            grdContact.FooterRow.FindControl("fupd_Certificate_Path").Focus();

        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();
            }

        }

    }
 
  
    /// <summary>
    /// To clear the text boxes, default selection of combos.
    /// </summary>
    /// <param name="blnClearMainId">Whether to clear Main Id.</param>
    private void ClearMe(bool blnClearMainId)
    {
        if (blnClearMainId == true)
        {
          
        }  
       

        grdContact.DataSource = null;
        grdContact.DataBind();
         
        EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Clear");
    }
 

    protected void btnClear_Click(object sender, EventArgs e)
    {
        ClearMe(true);
    } 

    protected void grdContact_RowCommand(object sender, GridViewCommandEventArgs e)
    {
        if (e.CommandName.Equals("Insert"))
        {
            try
            {
                TextBox txtDrill_Rec_Photo_Active = (TextBox)grdContact.FooterRow.FindControl("txtDrill_Rec_Photo_Active");

                FileUpload fupd_Certificate_Path = (FileUpload)grdContact.FooterRow.FindControl("fupd_Certificate_Path");

                if (fupd_Certificate_Path.HasFile)
                {
                    if (!clsMiscellaneous.CheckFile_Size("Photo", fupd_Certificate_Path.PostedFile.ContentLength, "MB", 5))
                        return;
                }

                clsHSE_Drill_Record_Photo_Upload _ObjMaster = new clsHSE_Drill_Record_Photo_Upload(strConString);

                _ObjMaster.Drill_Record_Hdr_Id = Convert.ToInt16(tbDrill_Record_Hdr_Id_Hidden.Value);                
               // _ObjMaster.Drill_Rec_Photo_Active = txtDrill_Rec_Photo_Active.Text;

                _ObjMaster.Certificate_Path_FileUploader = fupd_Certificate_Path;

                _ObjMaster.Cr_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
                _ObjMaster.InsertMe();
                               

                if ((_ObjMaster.ErrorString != "") && (_ObjMaster.ErrorString != null))
                {
                    throw new Exception(_ObjMaster.ErrorString);
                }
                //ScriptManager.RegisterStartupScript(this, this.GetType(), "MSG1", "<script>callpopup_ipwidth('Record inserted', 2000,'',220);</script>", false);

               FillGrid();
            }

            catch (SqlException sqlexep)
            {

                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
                ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Update", ErrorString);

                return;
            }
            catch (Exception exep)
            {

                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
                ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Update1", ErrorString);

                return;
            }
            finally
            {
            }
        }

        if (e.CommandName == "cmdDelete")
        {
            try
            {
                clsHSE_Drill_Record_Photo_Upload _ObjMaster = new clsHSE_Drill_Record_Photo_Upload(strConString);

                Int16 intDrill_Rec_Photo_Upload_Id = Convert.ToInt16(e.CommandArgument);

                GridViewRow gvr = (GridViewRow)(((LinkButton)e.CommandSource).NamingContainer);
                int RowIndex = gvr.RowIndex;

                HtmlInputHidden tbDrill_Rec_Photo_Delete_Path_Hiddden = (HtmlInputHidden)grdContact.Rows[RowIndex].FindControl("tbDrill_Rec_Photo_Upload_Path_Hidden");
               
                string strFile_Path = Server.MapPath("~/" + tbDrill_Rec_Photo_Delete_Path_Hiddden.Value);

                _ObjMaster.Drill_Rec_Photo_Delete_Path = strFile_Path;               
                _ObjMaster.Drill_Rec_Photo_Upload_Id = intDrill_Rec_Photo_Upload_Id;
                _ObjMaster.DeleteMe();             


                if ((_ObjMaster.ErrorString != "") && (_ObjMaster.ErrorString != null))
                {
                    throw new Exception(_ObjMaster.ErrorString);
                }
                ScriptManager.RegisterStartupScript(this, this.GetType(), "MSG1", "<script>callpopup_ipwidth('Record Deleted', 2000,'',220);</script>", false);
                FillGrid();
            }
            catch (SqlException sqlexep)
            {
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
                ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Update1", ErrorString);
                return;
            }
            catch (Exception exep)
            {
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
                ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Update1", ErrorString);
                return;
            }
            finally
            {
            }
        }
    }
     

    protected void grdContact_RowUpdating(object sender, GridViewUpdateEventArgs e)
    {
        try
        {
            Label lblId = (Label)grdContact.Rows[e.RowIndex].FindControl("lblId");

            TextBox txtEdit_Drill_Rec_Photo_Active = (TextBox)grdContact.Rows[e.RowIndex].FindControl("txtEdit_Drill_Rec_Photo_Active");
            FileUpload fupd_Certificate_Path_Edit_Item = (FileUpload)grdContact.Rows[e.RowIndex].FindControl("fupd_Certificate_Path_Edit_Item");

 

            if (fupd_Certificate_Path_Edit_Item.HasFile)
            {
                if (!clsMiscellaneous.CheckFile_Size("Photo", fupd_Certificate_Path_Edit_Item.PostedFile.ContentLength, "MB", 5))
                    return;
            }

            clsHSE_Drill_Record_Photo_Upload _ObjMaster = new clsHSE_Drill_Record_Photo_Upload(strConString);
            _ObjMaster.Drill_Rec_Photo_Upload_Id = Convert.ToInt16(lblId.Text);

            _ObjMaster.Drill_Rec_Photo_Active = txtEdit_Drill_Rec_Photo_Active.Text;
            _ObjMaster.Certificate_Path_FileUploader = fupd_Certificate_Path_Edit_Item;

            _ObjMaster.Mod_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
            _ObjMaster.UpdateMe();

            if ((_ObjMaster.ErrorString != "") && (_ObjMaster.ErrorString != null))
            {
                throw new Exception(_ObjMaster.ErrorString);
            }
            ScriptManager.RegisterStartupScript(this, this.GetType(), "MSG1", "<script>callpopup_ipwidth('Record Updated', 2000,'',220);</script>", false);
            grdContact.EditIndex = -1;
            FillGrid();

        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Update", ErrorString);
            return;
        }
        catch (Exception exep)
        {

            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Update1", ErrorString);
            return;
        }
        finally
        {
        }
    }

    protected void grdContact_RowCancelingEdit(object sender, GridViewCancelEditEventArgs e)
    {
        grdContact.EditIndex = -1;
        FillGrid(); 
    }

    protected void grdContact_RowEditing(object sender, GridViewEditEventArgs e)
    {
        grdContact.EditIndex = e.NewEditIndex;
        FillGrid();
    }



    protected void grdContact_RowDataBound(object sender, GridViewRowEventArgs e)
    {
        string strSystemURL = ConfigurationManager.ConnectionStrings["SystemURL"].ToString();

        if (e.Row.RowType == DataControlRowType.DataRow)
        {

            HtmlAnchor lnkDisp_Img = (HtmlAnchor)e.Row.FindControl("lnkDisp_Img");

            #region Show Photo


            HtmlInputHidden tbDrill_Rec_Photo_Upload_Path_Hidden = (HtmlInputHidden)e.Row.FindControl("tbDrill_Rec_Photo_Upload_Path_Hidden");

            if (!string.IsNullOrEmpty(tbDrill_Rec_Photo_Upload_Path_Hidden.Value))
            {
                string isPhotoUploaded = tbDrill_Rec_Photo_Upload_Path_Hidden.Value.Substring(0, 1);
                if (lnkDisp_Img != null)
                {
                    if (isPhotoUploaded.ToUpper().Trim() == "N")
                    {
                        lnkDisp_Img.Visible = false;
                    }
                    else
                    {  //Append the system Url with the image path To open image in Pop up.
                        lnkDisp_Img.Attributes.Add("onclick", "Image_Window('" + strSystemURL + tbDrill_Rec_Photo_Upload_Path_Hidden.Value + "');");
                    }
                }
            }
            #endregion
        }
    }
}




